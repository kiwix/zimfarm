#!/bin/bash
#
# Author : Florent Kaisser
#
# Usage : check_zim.sh <zimFilePath> <zimSrcDir> <zimDstDir> <zimQuarantineDir> <logDir> <zimCheckOptions> [NO_QUARANTINE|NO_CHECK]
#

ZIMCHECK=/usr/local/bin/zimcheck

ZIMFILE=$1
ZIMSRCDIR=$2
ZIMCHECK_OPTION=$6
OPTION=$7


ZIMPATH=$(echo $ZIMFILE | sed "s:$ZIMSRCDIR::")

DESTFILE=$3$ZIMPATH
DESTDIR=$(dirname $DESTFILE)

if [ "$OPTION" = "NO_QUARANTINE" ]
then
 QUARDIR=$DESTDIR
 QUARFILE=$DESTFILE
else
 QUARFILE=$4$ZIMPATH
 QUARDIR=$(dirname $QUARFILE)
fi

LOGFILE=$(echo "$5$ZIMPATH" | cut -f 1 -d '.').log
LOGDIR=$(dirname $5$ZIMPATH)

NAME_FORMAT="^(.+?_)([a-z\-]{2,10}?_|)(.+_|)([\d]{4}|)\-([\d]{2})$"
ZIM_NAME=$(basename "$ZIMPATH" .zim)

function moveZim () {
   mkdir -p $1
   mv -f $ZIMFILE $2
}

if [ "$OPTION" = "NO_CHECK" ]
then
  echo "move $ZIMFILE to $DESTFILE"
  moveZim $DESTDIR $DESTFILE
else
  mkdir -p $LOGDIR
  if $ZIMCHECK $ZIMCHECK_OPTION $ZIMFILE > $LOGFILE 2>&1
  then
   if (echo $ZIM_NAME | grep -q -P $NAME_FORMAT)
   then
    echo "$ZIMFILE is valid" >> $LOGFILE
    moveZim $DESTDIR $DESTFILE
   else
    echo "$ZIMFILE is valid but name is in an invalid format" >> $LOGFILE
    moveZim $QUARDIR $QUARFILE
   fi
  else
   echo "$ZIMFILE is not valid" >> $LOGFILE
   moveZim $QUARDIR $QUARFILE
  fi
fi
