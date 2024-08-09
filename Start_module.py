from Face_detection import Face_detection
from Connection_to_DB import Data_base
from Tracker import Tracker
import math
import torch
import cv2
from datetime import datetime
import pika
import json

def union(face_vectors,walk_vectors):
        
        res =[]
        cord_f =[]
        cord_w =[]
        #вычисление середины для сопоставления
        for vec in walk_vectors:
            cord_w.append(vec[0])

        for vector in face_vectors:
            cord_f.append( [vector[0][2]+(vector[0][0]- vector[0][2])/2,vector[0][3]])


        #поиск ближайших координат
        for i in range(len(cord_f)):
            min_d=1000000
            num =0

            for j in range(len(cord_w)):
                if math.dist(cord_f[i], cord_w[j])<min_d:
                    min_d =  math.dist(cord_f[i], cord_w[j])
                    num =j

            res.append([face_vectors[i][1],walk_vectors[num][1],cord_f[i]])
            cord_w.pop(num)
            walk_vectors.pop(num)
        
        #дописывание треков с нераспознанными векторами лица 
        for vector in walk_vectors:
              res.append([[0.0],vector[1],vector[0]])
              cord_w.pop(0)

        return res

print("Started")
capture = cv2.VideoCapture("/home/ebryzgalova/Downloads/zmExport_710990/241/241-video.mp4")#250, 248, 241
device = 'cuda' if torch.cuda.is_available() else 'cpu'
face_det =Face_detection('http://192.168.211.15', '8001',"7c970a58-40e1-4168-bd55-74dd76277752")
tracker = Tracker(device)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='persons_vectors')

camera =149
THINNING_CONSTANT = 5  # Берем каждый 5-тый кадр, можно задать любое значение, константа прореживания
frame_count = 0

status, frame = capture.read()

while status:  
    frame_count += 1  # Increment frame counter
    # Process only if frame_count is a multiple of THINNING_CONSTANT
    if frame_count % THINNING_CONSTANT == 0:            
        
        # вызов сервиса распознавания лиц
        face_vectors = face_det.calculate_vectors(frame)
        # вызов сервиса распознавания трека
        tracks =tracker.track(frame)
        if tracks:
            #объединение векторов лиц с треками
            q = union(face_vectors,tracks)
   
            for person in q:
                 cur_time = "'"+str(datetime.now())[0:19]+"'"
                 #отправка сообщениф в брокер
                 
                 message = {'camera':camera, 'time':cur_time,'face_vectors':person[0],'walk_vectors':person[0],'track_point_x':float(person[2][0]),'track_point_y':float(person[2][1]),'track':int(person[1])}
                 channel.basic_publish(exchange='',
                                       routing_key='persons_vectors',
                                       body=json.dumps(message),
                                       properties=pika.BasicProperties(
                                       delivery_mode = 5)) 
        status, frame = capture.read()          

             
      