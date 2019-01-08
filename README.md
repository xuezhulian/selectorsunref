# selectorsunref
iOS代码瘦身:未使用的方法

执行 python selectorsunref.py

输入的第一个参数为xxx.app，可以把Xcode products目录下的xxx.app拖到命令行，这个参数是为了拿到.app下的mach-o文件，分析使用的方法和未使用的方法。

输入的第二个参数是工程目录，这个参数是为了递归遍历找到工程中所有的.h文件，然后过滤掉包含的协议方法。
