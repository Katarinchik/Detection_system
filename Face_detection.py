import argparse
import cv2
import time
from threading import Thread

from compreface import CompreFace
from compreface.service import RecognitionService

class Face_detection:
    def __init__(self, host, port, api_key):
 
        self.results = []
        compre_face: CompreFace = CompreFace(host, port, {
            "limit": 0,
            "det_prob_threshold": 0.8,
            "prediction_count": 1,
            "face_plugins": "age,gender,calculator",
            "status": False
        }) 

        self.recognition: RecognitionService = compre_face.init_face_recognition(api_key)

    def calculate_vectors(self,frame):
        responce =[]
        self.frame = frame
        if not hasattr(self, 'frame'):
            return

        _, im_buf_arr = cv2.imencode(".jpg", self.frame)
        byte_im = im_buf_arr.tobytes()
        data = self.recognition.recognize(byte_im)
        self.results = data.get('result')
        #print(self.results)
        if self.results:
            results = self.results
            for result in results:
                box = result.get('box')
                box = [box['x_max'], box['y_max'],box['x_min'], box['y_min']]
                calculator =result.get('embedding')
                if box and calculator:
                    responce.append([box,calculator])
        return responce






        