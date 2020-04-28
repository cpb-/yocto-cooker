function textInFile
{
	expect=${3:-1}
	textInFileRange "$1" "$2" $expect $expect
}

function textInFileRange
{
	count=$(cat $1 | sed -r "s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]//g" | grep -P "$2"  | wc -l)
	if [ $count -lt $3 -o $count -gt $4 ]
	then
		echo "expected '$2' in $1 between $3 and $4 times - but found $count times"
		exit 1
	fi
}

function linesInFile
{
	count=$(cat $1 | wc -l)
	if [ $count -ne $2 ]
	then
		echo expected $2 lines in $1 but found $count
		exit 1
	fi
}

function fileOrDirExists
{
	expect=${4:-1}
	count=$(find $1 -name "$2" -type $3 | wc -l)
	if [ $count -ne $expect ]
	then
		echo "found $count files/dirs ($3) in $1 with '$2'-pattern where $expect expected"
		exit 1
	fi
}

function filesExist
{
	fileOrDirExists $1 $2 f $3
}

function dirsExist
{
	fileOrDirExists $1 $2 d $3
}

function fileExists
{
	filesExist $1 "*" 1
}

function assert_eq
{
	if [ "$1" != "$2" ]
	then
		echo expected $1, but got $2
		exit 1
	fi
}
