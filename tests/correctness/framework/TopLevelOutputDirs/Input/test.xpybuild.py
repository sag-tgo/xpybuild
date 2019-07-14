import os, logging
from propertysupport import *
from buildcommon import *
from pathsets import *

defineStringProperty('OUTPUT_DIR', None)
defineOutputDirProperty('OUTPUT_DIR1', '${OUTPUT_DIR}/out1')
defineOutputDirProperty('OUTPUT_DIR_NESTED1', '${OUTPUT_DIR}/out1/nested1')
defineOutputDirProperty('OUTPUT_DIR_NESTED2', '${OUTPUT_DIR}/out1/nested/2')
defineOutputDirProperty('OUTPUT_DIR_NESTED3', '${OUTPUT_DIR}/nested/../nested2')

defineOutputDirProperty('OUTPUT_DIR3', '${OUTPUT_DIR}/nested/../nested3')
defineOutputDirProperty('OUTPUT_DIR4', '${OUTPUT_DIR}/outputdir2')


from targets.writefile import *


WriteFile('${OUTPUT_DIR}/output.txt', lambda ctx: '\n'.join([x[x.find('build-output'):].replace('\\','/') for x in ctx.getTopLevelOutputDirs()]))
