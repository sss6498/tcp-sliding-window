import binascii
import socket as syssock
import struct
import sys
import random
import threading
import time

tPort = -1
rPort = -1
sockMain = (0,0)
currSeq = 0
hostAddr = ""
dataReceived = b""
sock352PktHdrData = '!BBBBHHLLQQLL'
lastAck = -1

version = 0x01;
#flags;
opt_ptr = 0x00;
protocol = 0x00;
header_len = 40;
checksum = 0x00;
source_port = 0x00;
dest_port = 0x00;
#sequence_no;
#ack_no;
#window = 0x00;
#payload_len;

#WILL BE SET TO TRUE AFTER ALL PACKETS ARE SENT
allAcked = False 
#CHANGES IN CONNECT METHOD
connectionExists = False
#WILL BE SET TO CLIENT/SERVER LATER
hostType = "temp"
#USED TO TEST DROPPED PACKET
hasBeenDropped = False
bufferLength = 262000
#USED TO CHECK WINDOW SIZE > PACKET SIZE
canSend = True
msgFull = b""
closeOk = False
spaceAvailable = 262*1024
termSignal = False

#GLOBAL FUNCTIONS ABOVE CLASS
def init(UDPportTx,UDPportRx):   # initialize your UDP socket here 
    global sockMain, tPort, rPort

    sockMain = syssock.socket(syssock.AF_INET, syssock.SOCK_DGRAM)
    rPort = int(UDPportRx)

    #if UDPportTx not defined, use same port for both receiving and transmitting
    if (UDPportTx == ''):
        tPort = rPort
    else:
        tPort = int(UDPportTx)
    #bind to '' to allow reception on all interfaces
    sockMain.bind(('', rPort))

    #set timeout to 0.2 sec
    sockMain.settimeout(0.2)
    print("SOCKET INITIALIZED!\n")

    return
    
class socket:
    
    def __init__(self):  # fill in your code here 
        print("Returning 352 Socket!\n")
        return
    
    def bind(self,address):
        print("BIND SUCCESSFUL!\n")
        return 

    def connect(self,address):  # fill in your code here 
        global sockMain, currSeq, hostType
        hostType = "Client"
        print("Initiating connection on %s\n" % (tPort))

        #create random sequence number
        currSeq = int(random.randint(20,100))
        
        #create packet header with SYN bit set in flags
        header = self.__headerMake(0x01, currSeq, 0, 0, 0)
        ackFlag = -1

        #set timeout, wait for ack of SYN, retransmit SYN packet
        while (ackFlag != currSeq + 1):
            #sendto method return number of bytes sent
            print("Attempting to connect...%d bytes sent!\n" % (sockMain.sendto(header, (address[0], tPort))))
            newHead = self.__packetRead()
            ackFlag = newHead[9]
        flag = newHead[1]
        if (flag == 0x05):
            print("No connection exists! Creating New Connection!\n") 
            #if ack has been received, connect
            #address[0] = IP address of the destination port, tPort = transmit port
            sockMain.connect((address[0], tPort))

            print("SOCKET CONNECTED!\n")
        elif (flag == 0x08):
            print("Connection Already Exists!\n")
        
        #update seq number for additional bytes that need to be transmitted
        currSeq += 1
        return 
    
    def listen(self,backlog):
        print("LISTENING!\n")
        return

    def accept(self):
        #(clientsocket, address) = (1,1)  # change this to your code 
        global sockMain, rPort, currSeq, connectionExists, hostType, bufferLock
        hostType = "Server"
        print("WAITING FOR CONNECTION ON %s\n" % (rPort))
        
        flag = -1
        newHead = b""
        #call __packetRead() until we get new connection

        while (flag != 0x01):
            newHead = self.__packetRead()
            flag = newHead[1]
        currSeq = newHead[8]
        if (connectionExists == True):
            #SETS RESET BIT IF CONNECTION ALREADY EXISTS
            flagReturn = 0x08
        else:
            #SETS BOTH ACK AND SYN BIT
            flagReturn = 0x05
            connectionExists = True
        
        #create random sequence number for seq num
        serverSeq = int(random.randint(20,100))

        #SEND HEADER TO CLIENT ACKING CONNECTION SETUP
        header = self.__headerMake(flagReturn, serverSeq, currSeq + 1, 0, 0)
        sockMain.sendto(header, hostAddr)
        currSeq += 1

        #CREATE LOCK FOR THE SERVER THREADS (RECV/RECVTOBUFFER)
        bufferLock = threading.Lock()
        #CREATE THREAD AND INITIALIZE THE THREAD
        currentSeq = 0
        recvToBufferThread = threading.Thread(target = self.recvToBuffer, args = (currentSeq,))
        recvToBufferThread.start()
        #CAN'T JOIN THREAD BECAUSE WE NEED ACCEPT TO FINISH BEFORE RECVTOBUFFER RETURNS

        print("ACQUIRED CONNECTION! CALLING INIT...\n")
        clientsocket = socket()
        return (clientsocket,hostAddr)

    def close(self):   # fill in your code here 
        global hostType

        if (hostType == "Client"):
            #CLIENT CLOSE
            self.clientClose()
        else:
            #SERVER CLOSE
            self.serverClose()

        return
         
    def clientClose(self):
        global hostType, sockMain

        newHead = b""

        print("%s Terminating Connection!\n" % hostType)
        #RANDOM SEQUENCE NUM
        terminal_no = random.randint(1, 20)
        #need to send FIN packet to terminate
        header = self.__headerMake(0x02, terminal_no, 0, 0, 0)
        flag = -1
        #SEND HANDSHAKE 1 UNTIL CLIENT RECEIVES HANDSHAKE 2
        while (flag != 0x06): 
            try:
                print("CLIENT SENT FIN\n")
                sockMain.sendto(header, hostAddr)
            except TypeError:
                sockMain.send(header)
            newHead = self.__packetRead()
            flag = newHead[1]
        terminalAck = newHead[8]
        print("CLIENT RECEIVED ACK + FIN, \n")
        #RECEIVE HANDSHAKE 2 AND SEND HANDSHAKE 3
        header = self.__headerMake(0x04, terminal_no + 1, terminalAck + 1, 0, 0)
        try:
            print("CLIENT SENT ACK\n")
            sockMain.sendto(header, hostAddr)
        except TypeError:
            sockMain.send(header)
        #CLOSE CLIENT SOCKET
        print("CLOSING CLIENT SOCKET\n")
        sockMain.close()

        return

    def serverClose(self):
        global hostType, sockMain, termSignal

        termSignal = True
        newHead = b""

        #need to send FIN packet to terminate
        print("%s Terminating Connection!\n" % hostType)
        #RANDOM SEQUENCE NUM
        terminal_no = random.randint(1, 20)

        flag = -1
        #RECEIVE HANDSHAKE 1
        while (flag != 0x02):
            newHead = self.__packetRead()
            flag = newHead[1]
        terminalAck = newHead[8]
        print("SERVER RECEIVED FIN\n")

        header = self.__headerMake(0x06, terminal_no, terminalAck + 1, 0, 0)
        flag = -1
        newHead = b""

        #SEND HANDSHAKE 2 UNTIL SERVER RECEIVES HANDSHAKE 3
        while (flag != 0x04): 
            try:
                sockMain.sendto(header, hostAddr)
                print("SERVER SENT FIN + ACK\n")
            except TypeError:
                sockMain.send(header)
            newHead = self.__packetRead()
            flag = newHead[1]

        #AFTER HANDSHAKE 3 RECEIVED, CLOSE SERVER SOCKET
        print("SERVER RECEIVED ACK\n")
        print("CLOSING SERVER SOCKET\n")
        sockMain.close()

        return
    def send(self, buffer):
        global currSeq, sockMain, lastAck, lock 
        lastAck = -1
        currSeq = 0

        print("STARTING SEND!\n")
        lock = threading.Lock()
        sendDataThread = threading.Thread(target = self.sendData, args = (buffer, lock))
        ackDataThread = threading.Thread(target = self.ackData, args = (buffer, lock))

        sendDataThread.start()
        ackDataThread.start()

        sendDataThread.join()
        ackDataThread.join()

        bytesSent = len(buffer)
        return bytesSent

    def sendData(self, buffer, lock):
        global sockMain, currSeq, allAcked, hasBeenDropped, spaceAvailable
        #timeBegin = time.time()
        allAcked = False
        msgLength = len(buffer)
        spaceAvailable = 262*1024


        msg = [buffer[i:i + 31000] for i in range(0, msgLength, 31000)]
        while (allAcked == False):

            #CHECK THAT RECVTOBUFFER CAN ACCEPT AN ADDITIONAL PACKET
            #IF NOT KEEP RUNNING WHILE LOOP UNTIL IT CAN
            if (spaceAvailable > 31000):    
                
                #print("%i\n" % currSeq)
                if (currSeq == len(msg)):
                    continue

                #TEST DROPPED PACKET
                #if (currSeq == 1):
                    #if (hasBeenDropped == False):
                        #print("Intentional delete Packet 1\n")
                        #hasBeenDropped = True
                        #continue

                currPacket = msg[currSeq]
                currPacketLength = len(currPacket)

                msgHeader = self.__headerMake(0x03, currSeq, 0, currPacketLength, 0)

                lock.acquire()
                #SEND PACKET TO SERVER
                sockMain.send(msgHeader + currPacket)
                currSeq += 1
                #print("SEND ATTEMPT %d" % spaceAvailable)
                #timeBegin = time.time()
                lock.release()
            else:
                #IF WE HIT THIS ELSE STATEMENT, BUFFER IS FULL
                print("BUFFER FULL! WAITING TO CLEAR OUT!")
        pass

    def ackData(self, buffer, lock):
        global currSeq, allAcked, lastAck, spaceAvailable
        msg = [buffer[i:i + 31000] for i in range(0, len(buffer), 31000)]
        timeBegin = time.time()

        #KEEP TRACK OF SPACE IN MSGFULL WITH VAR SPACEAVAILABLE
        spaceAvailable = 262*1024
        #SPACEOCCUPIED KEEPS TRACK OF LEN(BUFFER), NOT REALLY USED
        spaceOccupied = 0

        while True:
            newHead = self.__packetRead()
            
            if (newHead[1] == 0x09):
                #NEWHEAD[1] = 0x09 IS NEW FLAG WE CREATED TO CHECK IF BUFFER CLEARED OUT SPACE AND TO UPDATE SPACEAVAILABLE
                lock.acquire()
                spaceAvailable += newHead[10]
                lock.release()
            if ((newHead[0] == 0) and (time.time() >= timeBegin + 0.2)):
                lock.acquire()
                print("PACKET %i DROPPED!" % (lastAck + 1))
                currSeq = lastAck + 1
                #reset time
                timeBegin = time.time()
                lock.release()
            elif (newHead[0] != 0):
                lastAck = newHead[9]
                lock.acquire()
                #UPDATE SPACEOCCUPIED WITH MSGFULL LENGTH
                spaceOccupied = newHead[10]
                #CALCULATE HOW MUCH SPACE IS AVAILABLE TO SEND
                spaceAvailable = 262*1024 - newHead[10]
                lock.release()
                if (lastAck == len(msg) - 1):
                    break
        allAcked = True
        pass

    def recv(self,nbytes):
        global sockMain, msgFull, hostAddr, bufferLock, readyReceive
        #EXTRACT FROM BUFFER

        #READYRECEIVE MAKES SURE RECV DOESNT OCCUR UNTIL MSGFULL HAS AT LEAST NBYTES, GOT RID OF IT NOW
        readyReceive = False

        #print("RECV HIT")
        bufferSize = 262 *1024
        totalData =b""
        bytesReceived = 0

        #while (readyReceive == False):
        while (nbytes > len(msgFull)):
            #ONLY EXTRACT WHEN BUFFER CONTAINS ENOUGH TO SATISFY NBYTES EXTRACTION
            #print("NBYTES: %d" % nbytes)
            #print("MSGFULL: %d" % len(msgFull))
            continue
        bufferLock.acquire()
        #TOTALDATA IS WHAT IS BEING RECEIVED
        totalData = msgFull[:nbytes]
        #MSGFULL WILL SHIFT NBYTES TO RIGHT
        msgFull = msgFull[nbytes:len(msgFull)]

        #SEND HEADER WITH LENGTH OF DATA BEING RECEIVED
        header = self.__headerMake(0x09, 0, 0, 0, len(totalData))
        bufferLock.release()
        sockMain.sendto(header, hostAddr)
        return totalData

    def recvToBuffer(self, currentSeq):
        global sockMain, dataReceived, msgFull, hostAddr, bufferLock, termSignal, closeOk, readyReceive

        #print("RECVTOBUFFER HIT")
        dataReceived = b""
        receivedDataLength = False

        while (not termSignal):
            seqTracker = -1
            #check incoming packets until we receive correct seq num
            while (seqTracker != currentSeq):
                newHead = self.__packetRead()
                seqTracker = newHead[8]
                #print("MSGFULL: %d" % len(msgFull))
                #print("RECEIVED SEQUENCE NUMBER: %d \n" % seqTracker)
                if (seqTracker != currentSeq):
                    #SHOULD CONSTANTLY HIT UNTIL NEXT PACKET CONTAINS CORRECT SEQTRACKER
                    #print("EXPECTED SEQUENCE NUMBER: %d, DID NOT RECEIVE!" % currSeq)
                    if (termSignal):
                        #TERMSIGNAL SET TO TRUE WHEN ASKED TO CLOSE
                        return

            bufferLock.acquire()
            if (len(msgFull) + len(dataReceived) > 262*1024):
                #SHOULD STAY STUCK HERE UNTIL BUFFER HAS SPACE
                continue
            
            #ADD PACKET TO MSGFULL BUFFER
            msgFull += dataReceived
            #print("ADDED TO BUFFER")
            readyReceive = True
            #ack reception
            
            #len(msgFull) instead of 262*1024 - len(msgFull) - calculated in client side send method
            header = self.__headerMake(0x04, 0, seqTracker, len(dataReceived), len(msgFull))
            bufferLock.release()
            sockMain.sendto(header, hostAddr)

            #EXPECT NEXT PACKET
            currentSeq += 1

            if (not receivedDataLength and currentSeq == 1):
                #DEALS WITH ISSUE OF SENDING TWICE IN SERVER2-1.PY
                currentSeq = 0
                receivedDataLength = True 

        #closeOk = True            
        print("SUCCESSFULLY TERMINATED RECVTOBUFFER THREAD")
        return

    def __headerMake(self, flag, seqNum, ackNum, payLoad, win):
        global sock352PktHdrData, header_len, version, opt_ptr, protocol
        global checksum, source_port, dest_port

        #only 5 need to worry about, everything else taken from global
        flags = flag
        sequence_no = seqNum
        ack_no = ackNum
        payload_len = payLoad
        window = win

        #creates struct using format
        udpPkt_hdr_data = struct.Struct(sock352PktHdrData)

        #pack data into bytes and return it
        return udpPkt_hdr_data.pack(version, flags, opt_ptr, protocol, header_len, checksum, source_port, dest_port, sequence_no, ack_no, window, payload_len)
    
    def __packetRead(self):
        global sockMain, sock352PktHdrData, hostAddr, dataReceived

        #timeout after 0.2 sec
        try:
            (data, sendAddr) = sockMain.recvfrom(32000)
        except syssock.timeout:
            print("NO PACKETS RECEIVED BEFORE TIMEOUT!\n")
            emptyHdr = [0,0,0,0,0,0,0,0,0,0,0,0]
            return emptyHdr

        (dataHead, dataMsg) = (data[:40], data[40:])
        header = struct.unpack(sock352PktHdrData, dataHead)
        flag = header[1]

        if (flag == 0x01):
            #CONNECTION SETUP (SYN BIT)
            hostAddr = sendAddr
            return header
        elif (flag == 0x02):
            #CONNECTION TEARDOWN (FIN BIT)
            return header
        elif (flag == 0x03):
            #DATA PACKET
            dataReceived = dataMsg
            return header
        elif (flag == 0x04):
            #ACK PACKET
            return header
        elif (flag == 0x05):
            #BOTH ACK AND SYN BIT SET
            #SECOND HANDSHAKE IN 3WAY
            return header
        elif (flag == 0x06):
            #BOTH ACK AND FIN BIT SET
            #SECOND HANDSHAKE IN TEARDOWN
            return header
        elif (flag == 0x08):
            #RESET PACKET, IGNORE
            return header
        elif (flag == 0x09):
            #returns buffer size
            return header
        else:
            #ERROR IN PACKET, SEND RESET PACKET WITH SEQ NUM
            header = self.__headerMake(0x08, header[8], header[9], 0, 0)
            if (sockMain.sendto(header, sendAddr) > 0):
                print("RESET PACKET SENT!\n")
            else:
                print("FAILED TO SEND RESET PACKET!\n")

            return header
