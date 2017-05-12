#!/usr/bin/python

import os
import urllib
import urllib2
import json
import time
import base64
import string
import pprint
import websocket
import datetime


RANCHER_URL=os.environ.get('URL')
RANCHER_USER_NAME=os.environ.get('USER_NAME')
RANCHER_USER_KEY=os.environ.get('KEY')
STACK_NAME=""
SERVICE_NAME=""
STACK_SERVICE_NAME=os.environ.get('STACK_SERVICE_NAME')
SCALE_SIZE=os.environ.get('SCALE_SIZE')
CPU_SCALE_PERCENT = os.environ.get('CPU_SCALE_PERCENT')
MEM_SCALE_VALUE = os.environ.get('MEM_SCALE_VALUE')
SCAN_INTERVAL  = os.environ.get('SCAN_INTERVAL')
SCALE_RULE    = os.environ.get('SCALE_RULE')
SCALE_MIN_MATCH_TIME = os.environ.get('SCALE_MIN_MATCH_TIME')
SCALE_MIN = string.atoi(os.environ.get('SCALE_MIN'))
SCALE_MAX = string.atoi(os.environ.get('SCALE_MAX'))
CPU_SCALE_DOWN_PERCENT=os.environ.get('CPU_SCALE_DOWN_PERCENT')
MEM_SCALE_DOWN_VALUE=os.environ.get('MEM_SCALE_DOWN_VALUE')
#SCALE_MIN = 2
#SCALE_MAX = 6

RANCHER_URL="http://"+RANCHER_URL+":8080/v1/"

cpu_usage_percent = 0
mem_usage = 0
recv_msg_times=0
prev_user_cpu =0
prev_user_timestamp =""

s = STACK_SERVICE_NAME.split('/', 2)
if len(s) < 2:
    print("error: STACK_SERVICE_NAME in wrong format, STATCK_SERVICE_NAME = 'stack-name/service-name'")
    exit(1)
STACK_NAME  = s[0]
SERVICE_NAME = s[1]

def get_service_desc(username,key, url, stack, service):
    credential = urllib.urlencode({"username" : username, "password" : key})
    request = urllib2.Request(url+"environments?" + credential)
    base64key = base64.encodestring('%s:%s' % (username, key)).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64key)
    try:
        response = urllib2.urlopen(request)
        print("get service desc ok ")

    except IOError, e:
        print("Get stack info error: " + str(e.code))
        return None

    response = response.read()
    data = json.loads(response)
    for sk in data["data"]:
        if sk["name"] == STACK_NAME:
            request = urllib2.Request(sk["links"]["services"])
            request.add_header("Authorization", "Basic %s" % base64key)
            try:
                response = urllib2.urlopen(request)
            except IOError, e:
                print("Get service info error: " + str(e.code))
                return None
            response = response.read()
            data = json.loads(response)
            for svc in data["data"]:
                if svc["name"] == SERVICE_NAME:
                    print("find service ok")
                    return svc
            break
    print("Cannot find corresponding Stack/Service")    

    return None



def get_service_scale(desc):
    return desc["scale"]


def set_service_scale(desc,username,key,url,scale):
    print("newScale=" + str(scale))
    credential = urllib.urlencode({"username" : username, "password" : key})
    request = urllib2.Request(desc["actions"]["update"] + "&" + credential, "{\"scale\":" + str(scale) + "}")
    base64key = base64.encodestring('%s:%s' % (username, key)).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64key)
    request.add_header("Content-Type", "application/json")
    request.get_method = lambda: 'PUT'
    try:
        response = urllib2.urlopen(request)
    except IOError, e:
        print("Update service description error: " + str(e.code))
        return -1
    response = response.read()
    return 0   

def strtime_to_datetime(timestr):
    local_date_time = datetime.datetime.strptime(timestr,"%Y-%m-%dT%H:%M:%S.%f")
    return local_date_time


def get_cpu_usge(prev_timestamp,now_timestamp,prev_user_cpu,now_user_cpu,cpu_number):
    ret = 0
    time_str1= now_timestamp[:-9]
    time_str2= prev_timestamp[:-9]
    print prev_user_cpu
    print prev_timestamp
    print now_user_cpu
    print now_timestamp
    print time_str1
    datetime_t1 = strtime_to_datetime(time_str1)
    datetime_t2 = strtime_to_datetime(time_str2)

    d = datetime_t1 - datetime_t2
    ms= d.microseconds+ d.seconds*1000000
    print ms
    cpu_diff= now_user_cpu - prev_user_cpu
    print cpu_diff
    if ms > 0:
        cpu_diff/ms
        ret= ret/10
        ret= ret/cpu_number
    return ret





def on_message(ws, message):
    #    print   message
    global  recv_msg_times
    global  prev_user_cpu
    global  prev_user_timestamp
    recv_msg_times=recv_msg_times+1
    print recv_msg_times
    if recv_msg_times==75:
        data=json.loads(message)
        prev_user_cpu=data["cpu"]["usage"]["user"]
        prev_user_timestamp=data["timestamp"]
    if recv_msg_times < 80:
        return 

    data=json.loads(message)
    global mem_usage
    mem_usage=data["memory"]["usage"]/1048576
    global cpu_usage_percent
    now_user_cpu=data["cpu"]["usage"]["user"]
    now_user_timestamp=data["timestamp"]
    cpu_number=len(data["cpu"]["usage"]["per_cpu_usage"])

    cpu_usage_percent= get_cpu_usge(prev_user_timestamp,now_user_timestamp,prev_user_cpu,now_user_cpu,cpu_number)
    ws.close()


def on_error(ws, error):
    print "error" + error


def on_close(ws):
    print "### closed ###"


def on_open(ws):
    print "start"


def checkServiceContainerUsages(desc,username,key,cpu_limit,mem_limit,scale_rule):
    credential = urllib.urlencode({"username" : username, "password" : key}) 
    request = urllib2.Request(desc["links"]["instances"] + "?" + credential)
    base64key = base64.encodestring('%s:%s' % (username, key)).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64key)
    try:
        response = urllib2.urlopen(request)
        print("get instance ok ")

    except IOError, e:
        print("Get stack info error: " + str(e.code))
        return None

    response = response.read()
    data = json.loads(response)

    ret = 0    
    for sk in data["data"]:
        #        print sk["links"]["stats"]
        request = urllib2.Request(sk["links"]["stats"])
        request.add_header("Authorization", "Basic %s" % base64key)
        try:
            response = urllib2.urlopen(request)
        except IOError, e:
            print("Get container states  info error: " + str(e.code))
            return None
        response = response.read()
        data = json.loads(response)
#        print data["token"]
#        print data["url"]
        global mem_usage
        global cpu_usage_percent
        mem_usage=0
        cpu_usage_percent=0
        global recv_msg_times
        recv_msg_times=0

#        websocket.enableTrace(True)
        ws = websocket.WebSocketApp(data["url"]+"?token="+data["token"],on_message = on_message, on_error = on_error, on_close = on_close)
        ws.on_open = on_open
        ws.run_forever()
        print "cpu_usage_percent=",cpu_usage_percent
        print "mem_usage=",mem_usage

        if SCALE_RULE == "AND":
            print 'AND cpu_usage_percent=', cpu_usage_percent, ';CPU_SCALE_PERCENT=', CPU_SCALE_PERCENT,'mem_usage=', mem_usage, 'MEM_SCALE_VALUE=', MEM_SCALE_VALUE
            if cpu_usage_percent > int(CPU_SCALE_PERCENT) and mem_usage  > int(MEM_SCALE_VALUE):
                ret = 1
                break
            elif cpu_usage_percent < int(CPU_SCALE_DOWN_PERCENT) and mem_usage < int(MEM_SCALE_DOWN_VALUE):
                print '*****  AND cpu_usage_percent=', cpu_usage_percent, ';CPU_SCALE_PERCENT=', CPU_SCALE_PERCENT,'mem_usage=', mem_usage, 'MEM_SCALE_VALUE=', MEM_SCALE_VALUE
                ret = -1
                break  
        else:
            print 'OR cpu_usage_percent=', cpu_usage_percent, ';CPU_SCALE_PERCENT=', CPU_SCALE_PERCENT,'mem_usage=', mem_usage, 'MEM_SCALE_VALUE=', MEM_SCALE_VALUE
            if cpu_usage_percent > int(CPU_SCALE_PERCENT) or mem_usage  > int(MEM_SCALE_VALUE):
                ret =1
                break
            elif  cpu_usage_percent < int(CPU_SCALE_DOWN_PERCENT) or  mem_usage < int(MEM_SCALE_DOWN_VALUE):
            	print '******* OR cpu_usage_percent=', cpu_usage_percent, ';CPU_SCALE_PERCENT=', CPU_SCALE_PERCENT,'mem_usage=', mem_usage, 'MEM_SCALE_VALUE=', MEM_SCALE_VALUE
                ret=-1
                break

    return ret    



scale_min_match_time = 0

while 1:
        print RANCHER_USER_NAME
        print RANCHER_USER_KEY
        print RANCHER_URL
        print STACK_NAME
        print SERVICE_NAME
        desc=get_service_desc(RANCHER_USER_NAME,RANCHER_USER_KEY,RANCHER_URL,STACK_NAME,SERVICE_NAME)
        if desc != None:
            ret =checkServiceContainerUsages(desc,RANCHER_USER_NAME,RANCHER_USER_KEY,100,100,SCALE_RULE)
            print "checkServiceContainerUsages=",ret
#        if ret == 1:
#         scale_min_match_time=scale_min_match_time+1
#         print scale_min_match_time
#         if scale_min_match_time == int(SCALE_MIN_MATCH_TIME):
#            scale_min_match_time=0
            oldscale =  get_service_scale(desc)
            print("OldScale=" + str(oldscale))
            if ret == 1 :
                newscale = oldscale+int(SCALE_SIZE)
            elif ret == -1:
                newscale = oldscale-int(SCALE_SIZE)
            else:
                newscale=oldscale

            if not (SCALE_MIN <= newscale <= SCALE_MAX):
                if newscale > SCALE_MAX:
                    newscale=SCALE_MAX
            if newscale < SCALE_MIN:
                newscale=SCALE_MIN

                print("*****newscale=" + str(newscale))
            if newscale != oldscale:
                set_service_scale(desc,RANCHER_USER_NAME,RANCHER_USER_KEY,RANCHER_URL,newscale)
#        else:
#            scale_min_match_time=0
#        time.scale(float(SCAN_INTERVAL))
        time.sleep(float(SCAN_INTERVAL))
