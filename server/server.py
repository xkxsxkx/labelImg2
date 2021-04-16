import socket
from sys import executable
import time
import cv2
import numpy
import pyxcv as pv
from concurrent.futures import ThreadPoolExecutor
import threading
import hashlib
import logging
import json
from paddleocr import PaddleOCR, draw_ocr


class modelServer :
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.task_list = {}
        self.threads = []
        self.ocr = PaddleOCR(use_angle_cls = True, lang = "ch")
        self.model = None
    def recvAll(self, sock, count):
        buf = b''#buf是一个byte类型
        while count:
            #接受TCP套接字的数据。数据以字符串形式返回，count指定要接收的最大数据量.
            newbuf = sock.recv(count)
            if not newbuf: return None
            buf += newbuf
            count -= len(newbuf)
        return buf
    # 处理客户端的请求并执行事情
    def dealWithClient(self,newSocket,destAddr):
        while True:
            start = time.time()#用于计算帧率信息
            # method = newSocket.recv(1024).decode()
            received = newSocket.recv(1024).decode("utf-8")
            dictInfo = json.loads(received)
            print(dictInfo['method'])
            method = dictInfo['method']
            # length = self.recvAll(newSocket, 16)#获得图片文件的长度,16代表获取长度
            length = dictInfo['imgLen']
            # recvData = newSocket.recv(1024)
            print('connect from:'+str(destAddr))
            if length != None:
                stringData = self.recvAll(newSocket, length) #根据获得的文件长度，获取图片文件
                data = numpy.frombuffer(stringData, numpy.uint8) #将获取到的字符流数据转换成1维数组
                decImg = cv2.imdecode(data, cv2.IMREAD_COLOR) #将数组解码成图像
                cv2.imshow('SERVER', decImg)#显示图像
                k = cv2.waitKey(10)&0xff
                if k == 27:
                    break
                cv2.destroyAllWindows()
                if (method == 'make'):
                    self.model = pv.createTemplateRot(decImg, dictInfo['numLevels'],
                        dictInfo['angleStart'], dictInfo['angleExtent'], dictInfo['angleStep'],
                        dictInfo['granularity'], dictInfo['contrast'], dictInfo['minContrast'])
                elif (method == 'match'):
                    res = pv.bestMatchRotMg(decImg,
                        self.model, dictInfo['angleStart'], dictInfo['angleExtent'],
                        dictInfo['searchNum'], dictInfo['minScore'], dictInfo['greediness'])
                elif (method == 'ocr'):
                    result = self.ocr.ocr(decImg, cls=True)
                    ocrdata = {}
                    ocrdata["boxes"] = [line[0] for line in result]
                    ocrdata["ocr"] = [line[1][0] for line in result]
                    ocrdata["txts"] = [line[1][0] for line in result]
                    ocrdata["scores"] = [line[1][1] for line in result]
                    # ocrdata = json.dumps(result)
                    # newSocket.sendall(bytes(ocrdata.encode('utf-8')))
                    for line in result:
                        print(line)

            else:
                print('[%s]客户端已经关闭'%str(destAddr))
                break
            end = time.time()
            seconds = end - start
        newSocket.close()
    def addTask(self, newSocket, destAddr):
        t = threading.Thread(target=modelServer.dealWithClient, args=(self, newSocket, destAddr))
        t.start()

def main():
    serSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR  , 1)
    localAddr = ('', 8002)
    serSocket.bind(localAddr)
    serSocket.listen(5)
    ms = modelServer()
    try:
        while True:
            print('-----主进程，等待新客户端的到来------')
            newSocket,destAddr = serSocket.accept()

            print('-----主进程，接下来创建一个新的进程负责数据处理[%s]-----'%str(destAddr))
            ms.addTask(newSocket, destAddr)
            #因为线程中共享这个套接字，如果关闭了会导致这个套接字不可用，
            #但是此时在线程中这个套接字可能还在收数据，因此不能关闭
            #newSocket.close()
    finally:
        serSocket.close()
if __name__ == '__main__':
    main()