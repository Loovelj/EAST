if [ "$1" = "help" ]; then
    echo "bin/train.sh debug|console|stop|--model_name=xxxx --gpu=1"
    exit
fi

if [ "$1" = "stop" ]; then
    echo "!!!停止EAST训练!!!"
    ps aux|grep python|grep name=east_train|awk '{print $2}'|xargs kill -9
    exit
fi

Date=$(date +%Y%m%d%H%M)

# bin/train.sh --model=model.ckpt-74000
MODEL_NAME="None"
GPU=0
ARGS=`getopt -o g:m: --long gpu:,model_name: -- "$@"`
eval set -- "${ARGS}"
while true ;
do
    case "$1" in
        --model_name | -m)
            echo "加载预训练的模型：$2，继续训练。。。"
            MODEL_NAME=$2
            shift 2
            ;;
        --gpu | -g)
            echo "指定GPU：$2"
            GPU=$2
            shift 2
            ;;
        -- )
            shift ;
            break
            ;;
        * )
            echo "使用方式：bin/train.sh [debug] --gpu=1 --model=model.ckpt-74000"
            exit -1
            ;;
    esac
done

if [ "$MODEL_NAME" = "None" ]; then
    echo "未定义预加载模型文件名，重头开始训练！"
fi

if [ "$1" == "debug" ] || [ "$1" == "console" ]; then
    echo "###### 调试模式 ######"
    python -m train \
    --name=east_train \
    --debug=True \
    --gpu_list=$GPU \
    --max_steps=100 \
    --batch_size=1 \
    --num_readers=3 \
    --input_size=512 \
    --validate_steps=1 \
    --validate_batch_num=1 \
    --early_stop=100 \
    --save_summary_steps=1 \
    --model_path=./model \
    --model_name=$MODEL_NAME \
    --tboard_dir=./logs/tboard \
    --text_scale=512 \
    --training_data_path=./data/train \
    --validate_data_path=./data/validate \
    --geometry=RBOX \
    --learning_rate=0.0001 \
    --lambda_AABB=1000 \
    --lambda_theta=100000 \
    --lambda_score=1\
    --pretrained_model_path=./model/resnet_v1_50.ckpt
    exit
fi

echo "###### 生产模式 ######"
nohup \
    python -m train \
    --name=east_train \
    --debug=True \
    --gpu_list=$GPU \
    --max_steps=200000 \
    --batch_size=14 \
    --num_readers=100 \
    --input_size=512 \
    --validate_steps=1000 \
    --validate_batch_num=8 \
    --early_stop=100 \
    --save_summary_steps=100 \
    --model_path=./model \
    --model_name=$MODEL_NAME \
    --tboard_dir=./logs/tboard \
    --text_scale=512 \
    --training_data_path=./data/train \
    --validate_data_path=./data/validate \
    --geometry=RBOX \
    --learning_rate=0.0001 \
    --lambda_AABB=100 \
    --lambda_theta=10000 \
    --lambda_score=1\
    --pretrained_model_path=./model/resnet_v1_50.ckpt \
    >> ./logs/east_$Date.log 2>&1 &
