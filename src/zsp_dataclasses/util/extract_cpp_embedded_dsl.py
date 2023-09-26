#****************************************************************************
#* extract_cpp_embedded_dsl.py
#*
#* Copyright 2022 Matthew Ballance and Contributors
#*
#* Licensed under the Apache License, Version 2.0 (the "License"); you may 
#* not use this file except in compliance with the License.  
#* You may obtain a copy of the License at:
#*
#*   http://www.apache.org/licenses/LICENSE-2.0
#*
#* Unless required by applicable law or agreed to in writing, software 
#* distributed under the License is distributed on an "AS IS" BASIS, 
#* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  
#* See the License for the specific language governing permissions and 
#* limitations under the License.
#*
#* Created on:
#*     Author: 
#*
#****************************************************************************
from typing import List

#
#
#  ZSP_DATACLASSES(TestSuite_testname, RootComp, RootAction, R"(
#    @vdc.randclass
#    class MyC(object):
#      a : vdc.rand_uint32_t
#  )")
#
#

class DSLContent(object):
    def __init__(self,
                 name,
                 root_comp,
                 root_action,
                 content):
        self.name = name
        self.root_comp = root_comp
        self.root_action = root_action
        self.content = content

class ExtractCppEmbeddedDSL(object):

    def __init__(self, 
            file_or_fp,
            name=None,
            macro_name="ZSP_DATACLASSES"):
        self._macro_name = macro_name
        if hasattr(file_or_fp, "read"):
            # This is a stream-like object
            self._fp = file_or_fp
            if name is None:
                self._name = self._fp.name()
        else:
            self._fp = open(file_or_fp, "r")
            self._name = file_or_fp
        
        self._lineno = 0
        self._unget_ch = None
        self._last_ch = None
        self._buffer = ""
        self._buffer_i = 0

    def extract(self) -> List[DSLContent]:
        ret = []

        while self.find_macro():

            lineno = self._lineno
            while True:
                ch = self.getch()

                if ch is None or ch == '(':
                    break

            if ch is None:
                raise Exception("Failed to parse embedded DSL @ %s:%d" % (self._name, self._lineno))
            
            # Now, collect the complete content of the macro
            content = ""
            count_b = 1
            while count_b > 0:
                ch = self.getch()

                if ch is None:
                    break
                content += ch

                if ch == '(':
                    count_b += 1
                elif ch == ')':
                    count_b -= 1

            if count_b > 0:
                raise Exception("Unbalanced parens")
            content = content[:-2]
            
            # We now have text from a macro invocation
            start = 0
            count_b = 0
            params = []

            for i in range(len(content)):
                if content[i] == "," and count_b == 0:
                    params.append(content[start:i].strip())
                    start = i+1
                elif content[i] == '(':
                    count_b += 1
                elif content[i] == ')':
                    count_b -= 1

            if count_b != 0:
                raise Exception("Unbalanced parens while tokenizing") 

            if start < len(content):
                params.append(content[start:].strip())

            if len(params) != 4:
                raise Exception("Expected 3 params; received %d" % len(params))

            if params[-1].startswith('R"('):
                params[-1] = params[-1][3:-2]

            content = params[-1].split("\n")
            min_ws = 10000

            for l in content:
                l_strip = l.strip()
                if l_strip != "":
                    ws_l = len(l) - len(l_strip)
                    if ws_l < min_ws:
                        min_ws = ws_l

            for i in range(len(content)):
                content[i] = content[i][min_ws:]

            vsc_content = "\n".join(content)

            root_comp = params[1]
            root_action = params[2]

            info = DSLContent(params[0], root_comp, root_action, vsc_content)
            ret.append(info)

        self._fp.close()
        return ret

    def find_macro(self):

        while True:
            line = self._fp.readline()
            self._lineno += 1

            if line == "":
                break
            
            idx = line.find(self._macro_name)
            
            if idx >= 0:
                self._buffer = line
                self._buffer_i = idx + len(self._macro_name)
                return True
        
        return False

    def getch(self):
        if self._buffer is None:
            return None

        if self._buffer_i >= len(self._buffer):
            try:
                self._buffer = self._fp.readline()
                self._buffer_i = 0
                self._lineno += 1
                if self._buffer == "":
                    self._buffer = None
                    return None
            except Exception:
                self._buffer = None
                return None
            
        ret = self._buffer[self._buffer_i]
        self._buffer_i += 1
        return ret
    
    def ungetch(self, ch):
        if self._buffer is None:
            self._buffer = ch
        elif self._buffer_i > 0:
            self._buffer_i -= 1
            self._buffer[self._buffer_i] = ch
        else:
            self._buffer.insert(0, ch)

