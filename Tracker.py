import cv2
import numpy as np
import sys
import os
from ultralytics import YOLO
import torch
from torchvision import transforms
import torchreid.reid.models
from deep_sort_pytorch.deep_sort import DeepSort
from deep_sort_pytorch.utils.parser import get_config
np.int = int
np.float = float
class Tracker:
    def __init__(self,device):
        self.device = device
        sys.path.append(os.path.join(os.getcwd(), 'deep_sort_pytorch'))


        # Загрузка модели YOLOv8-Pose
        self.yolo_model = YOLO('yolov8n-pose.pt')  # Используйте ваш вес модели
        device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # Настройка модели ReID
        reid_model = torchreid.reid.models.build_model(name='osnet_x0_25', num_classes=1000, pretrained=True)
        self.reid_model = reid_model.to(device)
        self.reid_model.eval()

        # Создание файла конфигурации deep_sort.yaml
        config_file_path = "deep_sort_pytorch/configs/deep_sort.yaml"
        if not os.path.exists(config_file_path):
            print('not')
            os.makedirs(os.path.dirname(config_file_path), exist_ok=True)
            with open(config_file_path, "w") as f:
                f.write("""\
        DEEPSORT:
          REID_CKPT: "deep_sort_pytorch/resources/networks/mars-small128.pb"
          MAX_DIST: 0.2
          MIN_CONFIDENCE: 0.3
          NMS_MAX_OVERLAP: 1.0
          MAX_IOU_DISTANCE: 0.7
          MAX_AGE: 70
          N_INIT: 3
          NN_BUDGET: 100
        """)

        # Настройка DeepSORT
        cfg = get_config()
        cfg.merge_from_file(config_file_path)
        self.deepsort = DeepSort(
            model_path=cfg.DEEPSORT.REID_CKPT,
            max_dist=cfg.DEEPSORT.MAX_DIST, min_confidence=cfg.DEEPSORT.MIN_CONFIDENCE,
            nms_max_overlap=cfg.DEEPSORT.NMS_MAX_OVERLAP, max_iou_distance=cfg.DEEPSORT.MAX_IOU_DISTANCE,
            max_age=cfg.DEEPSORT.MAX_AGE, n_init=cfg.DEEPSORT.N_INIT, nn_budget=cfg.DEEPSORT.NN_BUDGET,
            use_cuda=True
        )
    def preprocess(self,img, device):
        transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((256, 128)),  # Размер изображения для модели ReID
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        img = transform(img).unsqueeze(0).to(device)
        return img
    def extract_reid_features(self,model, bboxes, frame, device):
        cropped_imgs = []
        for bbox in bboxes:
            x1, y1, x2, y2 = map(int, bbox)
            img_cropped = frame[y1:y2, x1:x2]
            img_cropped = self.preprocess(img_cropped, device)
            cropped_imgs.append(img_cropped)
        imgs_batch = torch.cat(cropped_imgs, dim=0)
        with torch.no_grad():
            features = model(imgs_batch)
        return features
    def track(self,frame):
    # Обнаружение объектов и скелетов с помощью YOLOv8-Pose #отключить вывод
        results =[]
        results = self.yolo_model(frame,show_labels =False,show_boxes = False,show_conf = False)
  

        bbox_xywh = []
        confs = []
        features = []
        centers =[]
        res=[]
        for result in results:
            
           
            bboxes = []
            for bbox, conf, cls,center in zip(result.boxes.xyxy, result.boxes.conf, result.boxes.cls,result.keypoints.xy):
                x1, y1, x2, y2 = bbox
                x_c, y_c, bbox_w, bbox_h = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
                obj = [x_c, y_c, bbox_w, bbox_h]
                bbox_xywh.append(obj)
                confs.append([conf.item()])
                bboxes.append(bbox) 
                centers.append(center[0])

            # Извлечение признаков ReID для батча bbox
            if bboxes:
            
                reid_features = self.extract_reid_features(self.reid_model, bboxes, frame, self.device)

                features.append(reid_features.cpu().numpy())

        # Обновление объектов в DeepSORT
        if bbox_xywh:
            
            xywhs = torch.Tensor(bbox_xywh)
            confss = torch.Tensor(confs)
            num_detections = len(xywhs)
            track_ids = np.arange(num_detections)

            outputs = self.deepsort.update(xywhs, confss, track_ids, frame)
            i=0
            for output in outputs:
                bbox_left, bbox_top, bbox_w, bbox_h, track_id, *_ = output
                
                res.append([[(bbox_left+bbox_w)/2,bbox_top],track_id])
                i+=1
        return(res)