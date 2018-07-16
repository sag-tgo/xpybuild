from pysys.constants import *
from xpybuild.xpybuild_basetest import XpybuildBaseTest
import io, collections

class PySysTest(XpybuildBaseTest):
	OPS = collections.OrderedDict([
	("""utils.fileutils.toLongPathSafe(OUTPUT_DIR+'/foo%010d0'%0)""",'toLongPathSafe_noop'),
	("""utils.fileutils.toLongPathSafe(OUTPUT_DIR+'/foo%010d/'%0)""",'toLongPathSafe_dir_caching'),
	("""utils.fileutils.toLongPathSafe(OUTPUT_DIR+'/foo%010d/'%ops)""",'toLongPathSafe_dir_nocaching'),
	("""utils.fileutils.toLongPathSafe(OUTPUT_DIR+'/foo%010d/../'%0)""",'toLongPathSafe_dirnormrequired_caching'),
	('isDirPath(OUTPUT_DIR)','isDirPath'), 
	('fileutils_isDirPath(OUTPUT_DIR)','fileutils_isDirPath'),
	('isWindows()','isWindows'), 
	("normpath(OUTPUT_DIR+'/'+str(ops))",'normpath(unique)'), 
	# deliberately make it always lowercase the drive letter on windows
	("normLongPath(OUTPUT_DIR[0].upper()+OUTPUT_DIR[1:]+'/'+str(ops))",'normLongPath(unique)'), 
	('BuildFileLocation()','BuildFileLocation'),
	("utils.fileutils.exists(OUTPUT_DIR+'/doesntexist')",'utils.fileutils.exists'),
	])


	def execute(self):
		for op in self.OPS:
			opname = self.OPS[op]
			bf = self.output+'/'+opname+'.xpybuild.py'
			with io.open(self.input+'/test.xpybuild.py') as f:
				contents = f.read()
			with io.open(bf, 'w') as f:
				f.write(contents.replace('@OP@', op))
			try:
				self.xpybuild(buildfile=bf, shouldFail=False, args=['-n'],stdouterr=opname)
			except Exception as e:
				self.addOutcome(BLOCKED, 'xpybuild failed for %s'%opname, abortOnError=False)

	def validate(self):
		for op in self.OPS:
			opname = self.OPS[op]
			try:
				self.reportPerformanceResult(float(self.getExprFromFile(opname+'.out', 'Microbenchmark operation took ([0-9.]+) ms each')), 
					'Time per call to %s'%opname, 'ms')
			except Exception as e:
				self.addOutcome(BLOCKED, 'missing output for %s: %s'%(opname, e), abortOnError=False)			