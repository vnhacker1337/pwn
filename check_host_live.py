# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import gevent
from gevent.queue import Queue
import argparse
from gevent import monkey
import requests
from gevent.pool import Pool
import fcntl
import os
from copy import deepcopy
import sys
import linecache



monkey.patch_all()
requests.packages.urllib3.disable_warnings()

red = "\033[91m"
end = "\033[00m"
blue = "\033[34m"
yellow = "\033[93m"
light_blue = '\033[96m'
purple = '\033[35m'
blue="\033[34m"


def parser_error(errmsg):
        print("Usage: python " + sys.argv[0] + " [Options] use -h for help")
        print("Error: " + errmsg)
        sys.exit()

def parse_args():
        # parse the arguments
        parser = argparse.ArgumentParser(
                epilog='\tExample: \r\npython ' + sys.argv[0] + " -i domain.txt -p 80,443")
        parser.error = parser_error
        parser._optionals.title = "OPTIONS"

        parser.add_argument(
                '-u', '--url', help="URL/domain to check it's Content")

        parser.add_argument(
                '-i',
                '--input',
                help='URL/domain list file to check their Content')

        parser.add_argument(
                '-t',
                '--threads',
                help='Number of threads to use for ports scan',
                type=int,
                default=20)
        parser.add_argument('-o', '--output', help='Save the results to text file')
        parser.add_argument('-p', '--ports', help='Add ports to scan.', default=None, nargs='*')

        args = parser.parse_args()
        if not (args.url or args.input):
                parser.error("No url inputed, please add -u or -i option")
        return args

def read_file(input_file):

        lines = linecache.getlines(input_file)
        return lines

def save_log(filename, msg):
        if filename:
                try:
                        f = open(filename, 'a+')
                        fcntl.lockf(f.fileno(), fcntl.LOCK_EX)
                        f.write(msg + "\n")
                        f.close()
                except Exception as e:
                        print(e)
                        print("Write file error.")
                        pass

def get_file(test_url, input_file, queue):
        if input_file:
                lines = read_file(input_file)
                for i in lines:
                        queue.put(i.strip())

def check_urls(url):

        headers = {"Cache-Control":"max-age=0",
                "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
                "Upgrade-Insecure-Requests":"1","Connection":"close",
                "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36",
                "Accept-Encoding":"gzip, deflate","Accept-Language":"vi,en-US;q=0.9,en;q=0.8"}
        try:
                resp = requests.head(url, headers=headers, timeout=10, verify=False)
                if resp.status_code:
                        print(purple + str(resp.status_code) + "\t" + url + end)
                        save_log(output, url)
        except Exception as e:
                pass

def check(queue):

        while not queue.empty():
                try:
                        item = queue.get(timeout=1.0)
                        check_urls(item)
                except Exception as e:
                        print(e)
                        break

def main():

        args = parse_args()
        queue = Queue()
        global output

        print(red + "Start check domains..." + end)
        if args.output:
                output = args.output
        else:
                timestamp = time.strftime("%Y-%m-%d-%H-%M-%S",
                                                                                          time.localtime())
                output = str(timestamp) + ".json"
                print("[Default]::Save log to: %s" % output)
        #Now queue is empty
        get_file(args.url, args.input, queue)

        threads = [gevent.spawn(check, queue) for i in range(args.threads)]
        try:
                gevent.joinall(threads)
        except KeyboardInterrupt as e:
                pass
        print(yellow + "Finished..." + end)

if __name__ == '__main__':
        main()

