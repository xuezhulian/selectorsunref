#!/usr/bin/python

import os
import re
import sys

reserved_prefixs = ["-[","+["]

def verified_app_path(path):
    if path.endswith('.app'):
        appname = path.split('/')[-1].split('.')[0]
        path = os.path.join(path, appname)
        if appname.endswith('-iPad'):
            path = path.replace(appname, appname[:-5])
    if not os.path.isfile(path):
        return None
    if not os.popen('file -b ' + path).read().startswith('Mach-O'):
        return None
    return path


def header_protocol_selectors(file_path):
    file_path = file_path.strip()
    if not os.path.isfile(file_path):
        return None
    protocol_sels = set()
    file = open(file_path, 'r')
    is_protocol_area = False
    for line in file.readlines():
        #delete description
        line = re.sub('\".*\"', '', line)
        #delete annotation
        line = re.sub('//.*', '', line)
        #match @protocol
        if re.compile('\s*@protocol\s*\w+').findall(line):
            is_protocol_area = True
        #match @end
        if re.compile('\s*@end').findall(line):
            is_protocol_area = False
        #match sel
        if is_protocol_area and re.compile('\s*[-|+]\s*\(').findall(line):
            sel_content_match_result = None
            if ':' in line:
                #match sel with parameters
                sel_content_match_result = re.compile('\w+\s*:').findall(line)
            else:
                #match sel without parameters
                sel_content_match_result = re.compile('\w+\s*;').findall(line)
            if sel_content_match_result:
                protocol_sels.add(''.join(sel_content_match_result).replace(';', ''))
    file.close()
    return protocol_sels


def protocol_selectors(path):
    print 'Get protocol selectors...'
    header_files = set()
    protocol_sels = set()
    system_base_dir = '/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk'
    #get system librareis
    lines = os.popen('otool -L ' + path).readlines()
    for line in lines:
        line = line.strip()
        #delete description
        line = re.sub('\(.*\)', '', line).strip()
        if line.startswith('/System/Library/'):
            library_dir = system_base_dir + '/'.join(line.split('/')[0:-1])
            if os.path.isdir(library_dir):
                header_files = header_files.union(os.popen('find %s -name \"*.h\"' % library_dir).readlines())

    project_dir = '/'.join(sys.path[0].strip().split('/')[0:-1])
    project_dir = raw_input('Please input project dir\nFor example:/Users/yuencong/workplace/xxx\n').strip()
    if not os.path.isdir(project_dir):
        exit('Error: project path error')
    header_files = header_files.union(os.popen('find %s -name \"*.h\"' % project_dir).readlines())
    for header_path in header_files:
        header_protocol_sels = header_protocol_selectors(header_path)
        if header_protocol_sels:
            protocol_sels = protocol_sels.union(header_protocol_sels)
    return protocol_sels


def imp_selectors(path):
    print 'Get imp selectors...'
    #return struct: {'setupHeaderShadowView':['-[TTBaseViewController setupHeaderShadowView]']}
    re_sel_imp = re.compile('\s*imp 0x\w+ ([+|-]\[.+\s(.+)\])')
    re_properties_start = re.compile('\s*baseProperties 0x\w{9}')
    re_properties_end = re.compile('\w{16} 0x\w{9} _OBJC_CLASS_\$_(.+)')
    re_property = re.compile('\s*name 0x\w+ (.+)')
    imp_sels = {}
    is_properties_area = False
    for line in os.popen('/usr/bin/otool -oV %s' % path).xreadlines():
        results = re_sel_imp.findall(line)
        if results:
            (class_sel, sel) = results[0]
            if sel in imp_sels:
                imp_sels[sel].add(class_sel)
            else:
                imp_sels[sel] = set([class_sel])
        else:
            #delete setter and getter methods as ivar assignment will not trigger them
            if re_properties_start.findall(line):
                is_properties_area = True
            if re_properties_end.findall(line):
                is_properties_area = False
            if is_properties_area:
                property_result = re_property.findall(line)
                if property_result:
                    property_name = property_result[0]
                    if property_name and property_name in imp_sels:
                        #properties layout in mach-o is after func imp
                        imp_sels.pop(property_name)
                        setter = 'set' + property_name[0].upper() + property_name[1:] + ':'
                        if setter in imp_sels:
                            imp_sels.pop(setter)
    return imp_sels


def ref_selectors(path):
    print 'Get ref selectors...'
    re_selrefs = re.compile('__TEXT:__objc_methname:(.+)')
    ref_sels = set()
    lines = os.popen('/usr/bin/otool -v -s __DATA __objc_selrefs %s' % path).readlines()
    for line in lines:
        results = re_selrefs.findall(line)
        if results:
            ref_sels.add(results[0])
    return ref_sels


def ignore_selectors(sel):
    if sel == '.cxx_destruct':
        return True
    if sel == 'load':
        return True
    return False


def filter_selectors(sels):
    filter_sels = set()
    for sel in sels:
        for prefix in reserved_prefixs:
            if sel.startswith(prefix):    
                filter_sels.add(sel)
    return filter_sels


def unref_selectors(path):
    protocol_sels = protocol_selectors(path)
    ref_sels = ref_selectors(path)
    if len(ref_sels) == 0:
        exit('Error: ref selectors count null')
    imp_sels = imp_selectors(path)
    if len(imp_sels) == 0:
        exit('Error: imp selectors count null')
    unref_sels = set()
    for sel in imp_sels:
        if ignore_selectors(sel):
            continue
        #protocol sels will not apppear in selrefs section
        if sel not in ref_sels and sel not in protocol_sels:
            unref_sels = unref_sels.union(filter_selectors(imp_sels[sel]))
    return unref_sels


if __name__ == '__main__':
    path = raw_input('Please input app path\nFor example:/Users/yuencong/Library/Developer/Xcode/DerivedData/xxx/Build/Products/Dev-iphoneos/xxx.app\n').strip()
    path = verified_app_path(path)
    if not path:
        exit('Error: invalid app path')
    unref_sels = unref_selectors(path)
    f = open(os.path.join(sys.path[0].strip(), 'selectorunrefs.txt'), 'w')
    f.write('selectorunrefs count: %d\n' % len(unref_sels))
    for unref_sel in unref_sels:
        print 'unref selector: %s' % unref_sel
        f.write(unref_sel + '\n')
    f.close()
    print('Done! %d selectors is unreferenced, selectorunref.txt has already stored in script dir.' % len(unref_sels))