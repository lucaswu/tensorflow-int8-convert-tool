#! /bin/bash
CurrentDir=$PWD
rm -f "$CurrentDir/vs_scale.h"

echo "#pragma once" >>"$CurrentDir/vs_scale.h"

function getdir(){ 
    kernelList=`ls $1`
    for fileName in $kernelList
    do 
       
        dir=$1/$fileName
        if [ -f $dir ];then
            lastfile=${dir#*$PWD/}
            xxd -i $lastfile >> "$CurrentDir/vs_scale.h"
            if [ $? -ne 0 ];then
                echo " no $fileName !"
                exit 1
            fi
            
        elif test -d $dir;then
            getdir $dir
        fi
    done

}
getdir $1