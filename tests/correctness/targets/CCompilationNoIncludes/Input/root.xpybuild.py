#
# Copyright (c) 2019 Software AG, Darmstadt, Germany and/or its licensors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
from propertysupport import *
from buildcommon import *
from pathsets import *

from targets.native import *
from targets.copy import Copy
from utils.compilers import GCC, VisualStudio

include('../../../../build_utilities/native_config.xpybuild.py')

setGlobalOption('native.include.upToDateCheckIgnoreSystemHeaders', True) # only works on linux/gcc currently

objs = [C(objectname("${BUILD_WORK_DIR}/obj/"+cpp), "./%s.c" % cpp,
	) for cpp in ['test'] ]

Link(exename("${OUTPUT_DIR}/test"), objs)
