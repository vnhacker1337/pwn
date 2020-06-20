import linecache
import sys
import os

def get_file(filename):
        lines = linecache.getlines(filename)
        return lines

def parseToDomain(lines):

        for line in lines:
                mapData = line.strip().split("\t")
                # print(mapData[1])
                for port in mapData[1].split(","):

                        if port == "80":
                                url = "http://" + mapData[0] + ":" + port
                                print(url)
                        elif port.endswith("443"):
                                url = "https://" + mapData[0] + ":" + port
                                print(url)
                        else:
                                url = "http://" + mapData[0] + ":" + port
                                print(url)
                                url = "https://" + mapData[0] + ":" + port
                                print(url)

def main():
        lines = get_file(sys.argv[1])
        parseToDomain(lines)

if __name__ == '__main__':
        main()
