'''
this file is modified from keras implemention of data process multi-threading,
see https://github.com/fchollet/keras/blob/master/keras/utils/data_utils.py
'''
import time
import numpy as np
import threading
import multiprocessing
import logging
import cv2

logger = logging.getLogger(__name__)

try:
    import queue
except ImportError:
    import Queue as queue


class GeneratorEnqueuer():
    """Builds a queue out of a data generator.

    Used in `fit_generator`, `evaluate_generator`, `predict_generator`.

    # Arguments
        generator: a generator function which endlessly yields data
        use_multiprocessing: use multiprocessing if True, otherwise threading
        wait_time: time to sleep in-between calls to `put()`
        random_seed: Initial seed for workers,
            will be incremented by one for each workers.
    """

    def __init__(self, generator,
                 use_multiprocessing=False,
                 wait_time=0.05,
                 random_seed=None):
        self.wait_time = wait_time
        self._generator = generator
        self._use_multiprocessing = use_multiprocessing
        self._threads = []
        self._stop_event = None
        self.queue = None
        self.random_seed = random_seed

    def start(self, workers=1, max_queue_size=10):
        """Kicks off threads which add data from the generator into the queue.

        # Arguments
            workers: number of worker threads
            max_queue_size: queue size
                (when full, threads could block on `put()`)
        """
        import os
        def data_generator_task():
            logger.info("启动的进程PID:%r",os.getpid())
            from utils.debug_tool import enable_pystack
            enable_pystack()
            #logger.debug('1')
            while not self._stop_event.is_set():
                #logger.debug('2')
                try:
                    if self._use_multiprocessing or self.queue.qsize() < max_queue_size:
                        #logger.debug('3')
                        load_time = time.time()
                        generator_output = next(self._generator)
                        # logger.debug("进程[%d],加载一批数据，时间%f",os.getpid(),(time.time() - load_time))
                        #logger.debug('4')
                        self.queue.put(generator_output)
                    else:
                        #logger.debug('5')
                        time.sleep(self.wait_time)
                except Exception:
                    self._stop_event.set()
                    raise

        try:
            if self._use_multiprocessing:
                logger.info("创建共享的Queue：%d",max_queue_size)
                self.queue = multiprocessing.Queue(maxsize=max_queue_size)
                self._stop_event = multiprocessing.Event()
            else:
                logger.info("we use multi-thread...")
                self.queue = queue.Queue()
                self._stop_event = threading.Event()

            for _ in range(workers):
                if self._use_multiprocessing:
                    # Reset random seed else all children processes
                    # share the same seed
                    np.random.seed(self.random_seed)
                    thread = multiprocessing.Process(target=data_generator_task)
                    thread.daemon = True
                    if self.random_seed is not None:
                        self.random_seed += 1
                else:
                    thread = threading.Thread(target=data_generator_task)
                self._threads.append(thread)
                thread.start()
        except:
            self.stop()
            raise

    def is_running(self):
        return self._stop_event is not None and not self._stop_event.is_set()

    def stop(self, timeout=None):
        """Stops running threads and wait for them to exit, if necessary.

        Should be called by the same thread which called `start()`.

        # Arguments
            timeout: maximum time to wait on `thread.join()`.
        """
        if self.is_running():
            self._stop_event.set()

        for thread in self._threads:
            if thread.is_alive():
                if self._use_multiprocessing:
                    thread.terminate()
                else:
                    thread.join(timeout)

        if self._use_multiprocessing:
            if self.queue is not None:
                self.queue.close()

        self._threads = []
        self._stop_event = None
        self.queue = None

    def get(self):
        """Creates a generator to extract data from the queue.

        Skip the data if it is `None`.

        # Returns
            A generator
        """
        while self.is_running():
            if not self.queue.empty():
                inputs = self.queue.get()
                if inputs is not None:
                    yield inputs
            else:
                time.sleep(self.wait_time)


# 调试50张（循环覆盖），可用使用python simple-http 8080（python自带的）启动一个简单的web服务器，来调试
def debug_draw_box(image,boxes,name,index,label):
    for i, box in enumerate(boxes):
        cv2.polylines(image, box[:8].reshape((-1, 4, 2)).astype(np.int32),isClosed=True,color=(0,0,255),thickness=1) #red

    # 如果标签不为空，画之
    if label is not None:
        for i, lbox in enumerate(label):
            cv2.polylines(image, lbox[:8].reshape((-1, 4, 2)).astype(np.int32),isClosed=True,color=(255,0,0),thickness=1) #green
        # logger.debug("【调试】画GT：%r",label)

    cv2.imwrite("debug/{}_{}.jpg".format(index,name),image)

# 按比例调整一张图的框的坐标,bboxes是[[[x1, y1], [x2, y2], [x3, y3], [x4, y4],],]也就是[M,4,2]，M是框个数，4是4个点，2是x/y
def resize_box(ratio_h,ratio_w,bboxes):
    # logger.debug("图像的标示框的shape：%r",bboxes.shape)
    # logger.debug("图像的标示框1：%r", bboxes)
    bboxes[:, :, 0] *= ratio_w
    bboxes[:, :, 1] *= ratio_h
    # logger.debug("图像的标示框2：%r", bboxes)

# 调整宽高为32的倍数，宽高不能大于2400
def resize_image(im, max_side_len=2400):
    '''
    resize image to a size multiple of 32 which is required by the network
    :param im: the resized image
    :param max_side_len: limit of max image size to avoid out of memory in gpu
    :return: the resized image and the resize ratio
    '''
    h, w, _ = im.shape

    resize_w = w
    resize_h = h

    # limit the max side
    if max(resize_h, resize_w) > max_side_len:
        logger.debug("图像太大了（大约%d），需要resize[h=%d,w=%d]",max_side_len,h,w)
        ratio = float(max_side_len) / resize_h \
            if resize_h > resize_w \
            else float(max_side_len) / resize_w
    else:
        ratio = 1.
    resize_h = int(resize_h * ratio)
    resize_w = int(resize_w * ratio)

    resize_h = resize_h if resize_h % 32 == 0 else (resize_h // 32 - 1) * 32
    resize_w = resize_w if resize_w % 32 == 0 else (resize_w // 32 - 1) * 32
    resize_h = max(32, resize_h)
    resize_w = max(32, resize_w)

    new_size= (int(resize_w), int(resize_h))
    im = cv2.resize(im,new_size )
    logger.debug("图像[W,H] Resize，从%r=>%r",(w,h),new_size)

    ratio_h = resize_h / float(h)
    ratio_w = resize_w / float(w)

    return im, ratio_h, ratio_w