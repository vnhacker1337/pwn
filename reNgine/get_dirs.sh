!/bin/sh

if [[ $# -eq 5 ]]
then
timeout 500 python3 /app/tools/dirsearch/dirsearch.py -u $1 -w $2 --json-report=$3 -e $4 -t $5 -e $4 -i 200,403,405 --exclude-texts=Attack Detected,Please contact the system administrator
else
timeout 500 python3 /app/tools/dirsearch/dirsearch.py -u $1 -w $2 --json-report=$3 -e $4 -t $5 -r -R $6 -e $4 -i 200,403,405 --exclude-texts=Attack Detected,Please contact the system administrator
fi

# if [[ $# -eq 5 ]]
# then
# ffuf -u $1 -w $2 -o $3 -D -e $4 -mc 200,403,405,302,301 -ac -se

# cat $3 | jq '[.results[]|{status: .status, length: .length, url: .url}]' | grep -oP "status\":\s(\d{3})|length\":\s(\d{1,7})|url\":\s\"(http[s]?:\/\/.*?)\"" | paste -d' ' - - - | awk '{print $2"   "$4"    "$6}' | sed 's/\"//g' > clear.$3
# mv clear.$3 $3
# fi