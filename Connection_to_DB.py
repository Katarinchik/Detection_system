from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType
import random
class Data_base:
    def __init__(self,port,host,collection_name):
        self.port = port
        self.host = host
        self.collection_name =collection_name
        connection =connections.connect("default", host=self.host, port= self.port) 
        self.collection = Collection(collection_name)

    def add_to_bd(self,camera,track =None,time=None,vector1=None,vector2=None,person_id = None):
        entities = []
        if person_id:
            entities.append([person_id])
            print(person_id)
        entities.append([camera])
        if time:
            entities.append([time]) 
        if track:
            entities.append([track])
        if vector1:
            entities.append([vector1])
        if vector2:
            entities.append([vector2])

        self.collection.insert(entities)
 

    def get_data_from_bd(self,output_fields):

        result = self.collection.query(expr='',output_fields=output_fields, limit =1)
      
        return result
    
    def delete_person(self,id):
        
        expr = f"person_id in [{id}]"
        self.collection.delete(expr)

    def check_db(self):
        self.collection.load()
        result = self.collection.query(expr='',output_fields=["person_id"],limit =10)#,"id", "camera", "time","track","face_vectors","walk_vectors"
        print(result)

    def search_similar_vectors(self,camera,vector,anns_field):
    
        self.collection.load()
        search_params = {
        "metric_type": "L2", 
        "offset": 0, 
        "ignore_growing": False, 
        "params": {"nprobe": 10}
        }
        results = self.collection.search(
        data=[vector], 
        anns_field="face_vectors", 

        param=search_params,
        limit=1,
        expr=f"camera in [{camera}]",

        output_fields=['person_id'],
        consistency_level="Strong"
            )       
        return results
    



