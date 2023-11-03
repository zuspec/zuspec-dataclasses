#****************************************************************************
#* __main__.py
#*
#* zsp_dataclasses.util.gen_cpp_dt_defs
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

import argparse
import os
import zsp_dataclasses as zdc
from zsp_dataclasses.impl.ctor import Ctor
from zsp_dataclasses.impl.pyctxt.context import Context
from zsp_dataclasses.impl.generators.zsp_data_model_cpp_gen import ZspDataModelCppGen
from ..extract_cpp_embedded_dsl import ExtractCppEmbeddedDSL

def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o","--outdir", default="zspdefs",
        help="Specifies the output directory")
    parser.add_argument("-d", "--depfile",
        help="Specifies a dependency file")
    parser.add_argument("files", nargs='+')

    return parser

def main():
    parser = get_parser()
    args = parser.parse_args()

    deps_ts = None
    if args.depfile is not None and os.path.isfile(args.depfile):
        deps_ts = os.path.getmtime(args.depfile)

    fragment_m = {}
    for file in args.files:
        print("Process %s" % file)
        if deps_ts is not None:
            file_ts = os.path.getmtime(file)
            if file_ts <= deps_ts:
                print("Skip due to deps")
                continue

        fragments = ExtractCppEmbeddedDSL(file).extract()
        print("fragments: %s" % str(fragments))

        for f in fragments:
            if f.name in fragment_m.keys():
                raise Exception("Duplicate fragment-name %s" % f.name)
            fragment_m[f.name] = f

    if not os.path.isdir(args.outdir):
        os.makedirs(args.outdir, exist_ok=True)

    for fn in fragment_m.keys():
        Ctor.init(Context())

        print("--> Process Fragment %s" % fn)
        _globals = globals().copy()
        exec(fragment_m[fn].content, _globals)
        print("<-- Process Fragment %s" % fn)

        Ctor.inst().elab()

        header_path = os.path.join(args.outdir, "%s.h" % fn)
        root_comp = Ctor.inst().ctxt().findDataTypeComponent(fragment_m[fn].root_comp)
        if root_comp is None:
            raise Exception("Failed to find root component %s" % fragment_m[fn].root_comp)
        root_action = Ctor.inst().ctxt().findDataTypeAction(fragment_m[fn].root_action)
        if root_action is None:
            raise Exception("Failed to find root action %s" % fragment_m[fn].root_action)
        gen = ZspDataModelCppGen()
        gen._ctxt = "m_ctxt"
        with open(header_path, "w") as fp:
            fp.write(gen.generate(
                root_comp, 
                root_action, 
                Ctor.inst().ctxt().getDataTypeFunctions()))

    if args.depfile is not None:
        with open(args.depfile, "w") as fp:
            fp.write("\n")

if __name__ == "__main__":
    main()

