from Connection_to_DB import Data_base
from datetime import datetime
import time
import pika, sys, os
import json
import psycopg2

con = psycopg2.connect(dbname="nicdb", host="192.168.250.1", user="postgres", password="12345678", port="5432")
cur = con.cursor()

# запрос в таблицу имен и должностей для добавления нового человека и вычисления его id
def get_last_id():
    cur.execute("SELECT MAX(id) FROM persons")
    last_id=cur.fetchall()[0][0]+1
    cur.execute("INSERT INTO persons (first_name, last_name, position) VALUES ("+str(last_id)+","+str(last_id)+","+str(last_id)+") ")
    con.commit()   
    return last_id

# класс для хранения данных о появлении и передвижениях людей в кадре
class Person():

    def __init__(self,track,person_id,time_in,camera,track_point):
        
        self.camera = camera # снимавшая камера
        self.num =0# количество кадров, в которых появился объект (костыль для тестирования)
        self.track = track# трек объекта
        if person_id!=0:
            self.person_id = []# все id, распознанные для данного трека
        else:
            self.person_id = [[person_id],[1]]# все id, распознанные для данного трека
   
        self.time_in = time_in# время появления в кадре
        self.time_out = time_in# время выхода из кадра
        self.track_line =[track_point]# траектория человека

    def update(self,time_out,person_id,track_point):#обновление объекта - изменяем время выхода из кадра иобновляем список определенных id для данного объектаtrack_point,

        # если распознанный id имеется в списке, увеличиваем его количество, если нет - добавляем в список
        # есди id не распознан - ничего не добавляем
        if person_id in self.person_id[0]:
            self.person_id[1][self.person_id[0].index(person_id)]+=1
        elif person_id!=0:
            self.person_id[0].append(person_id)
            self.person_id[1].append(1)
        
        self.time_out=time_out
        self.num+=1
        self.track_line.append(track_point)
        
    def send_to_db(self):#запись объектов в бд
        if self.person_id:
            #нахождение самого часто встречающегося id
            max_id= self.person_id[0][self.person_id[1].index(max(self.person_id[1]))]
        else:
            max_id=0
        # вставка данных объекта в бд
        insert =str(self.camera)+','+str(max_id)+','+self.time_in+','+self.time_out
        cur.execute('''INSERT INTO Events (Camera, Person_id, Time_in, Time_out) VALUES ('''+insert+''') ''')
        con.commit()  

global persons
def main():  
    threadhold = 3 #интервал для записи объектов в бд (часы)
    max_interval =20 #максимальный интервал для сохранения трека за изначальным объектом (секунды)

    # инициализация баз данных с образцами известных походок и лиц 
    face_db =Data_base( "19530","192.168.211.15","Known_face")
    gait_db =Data_base( "19530","192.168.211.15","Known_gait")

    persons =[]

    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='persons_vectors')

    def callback(ch, method, properties, body):
        # чтение сообщения из брокера
        res =json.loads(body)

        #если вектор лица был рассчитан, пробуем идентифицировать человека
        if res['face_vectors']!=[0.0]:
            face_id = face_db.search_similar_vectors(res['camera'],res['face_vectors'],'face_vectors')[0][0].entity.get('person_id')
            gait_id = face_id#gait_db.search_similar_vectors(res['camera'],res['walk_vectors'],'walk_vectors')

            # если id лица и походки есть, и они совпадают,
            if face_id and gait_id and face_id == gait_id:
                res_id = face_id
            # если id лица и походки есть, но они не совпадают, добавляем в базы нового человека
            elif face_id and gait_id and face_id!=gait_id:
           
                res_id = get_last_id()
                gait_db.add_to_bd(vector1= res['walk_vectors'],camera= res['camera'], person_id =res_id)
                face_db.add_to_bd(vector1= res['face_vectors'],camera= res['camera'], person_id =res_id)       

            # если не найден id походки, но найден id лица, добавляем в базу данных походки новую запись с id лица
            elif not gait_id and face_id:
            
                res_id = face_id
                gait_db.add_to_bd(vector1= res['walk_vectors'],camera= res['camera'], person_id =face_id)

            # если не дайдены id лица и походки, добавляем в базы нового человека
            elif gait_id and not face_id:

                res_id = gait_id
                face_db.add_to_bd(vector1= res['face_vectors'],camera= res['camera'], person_id =gait_id)


            # если не найден id лица, но найден id походки, добавляем в базу данных лиц новую запись 
            else :
                res_id = get_last_id()
                gait_db.add_to_bd(vector1= res['walk_vectors'],camera= res['camera'], person_id =res_id)
                face_db.add_to_bd(vector1= res['face_vectors'],camera= res['camera'], person_id =res_id)
                
        # если вектор лица был рассчитан, считаем, что человек не распознан и присваиваем id = 0
        else:
            res_id = 0
        f=True
    
        # поиск текущего трека среди имеющихся объектов по номеру трека и камере
        for i in range(len(persons)):

            if persons[i].track == res['track'] and persons[i].camera == res['camera']:

                #если человека с найденным треком долго небыло в кадре, считаем, что трек присвоился новому человеку. 
                #пишем данные текущегшо в базу, удаляем из списка и создаем новый объект
                if (datetime.strptime(res['time'][1:19], '%Y-%m-%d %H:%M:%S') -datetime.strptime(persons[i].time_out[1:19], '%Y-%m-%d %H:%M:%S')).seconds>max_interval:
                    persons[i].send_to_db()
                    persons.pop(i)
                    persons.append(Person(res['track'],res_id,res['time'],res['camera'],[res['track_point_x'],res['track_point_y']]))
                else:
                    persons[i].update(res['time'],res_id,[res['track_point_x'],res['track_point_y']])
                
                f=False
            #костыль для тестирования - запись в бд после 5 появлений
            if persons[i].num > 5:
                 persons[i].send_to_db()

        # если среди имеющихся объектов текущий трек не найден, создаем новый объектт
        if f:
            persons.append(Person(res['track'],res_id,res['time'],res['camera'],[res['track_point_x'],res['track_point_y']]))

        # запись данных в бд раз в несколько часов
        if datetime.now().time().hour % threadhold==0 and datetime.now().time().minute ==0:
            for person in persons:
                person.send_to_db()
            persons.clear()


    channel.basic_consume(queue='persons_vectors', on_message_callback=callback, auto_ack=True)
    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    
        try:
            main()
        except KeyboardInterrupt:
            print('Interrupted')
            try:
                sys.exit(0)
            except SystemExit:
                os._exit(0)

   













