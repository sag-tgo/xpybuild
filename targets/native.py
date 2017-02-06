# xpyBuild - eXtensible Python-based Build System
#
# Copyright (c) 2013 - 2017 Software AG, Darmstadt, Germany and/or its licensors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# $Id: native.py 301527 2017-02-06 15:31:43Z matj $
#

import os, inspect, re, string, time

from buildcommon import *
from basetarget import BaseTarget
from propertysupport import defineOption
from utils.process import call
from pathsets import PathSet, BasePathSet
from buildcontext import getBuildInitializationContext
from buildexceptions import BuildException
from propertyfunctors import make_functor, Composable
from utils.compilers import DefaultCompilers
from utils.fileutils import openForWrite, mkdir, deleteFile, getmtime, exists, normLongPath

defineOption('native.compilers', DefaultCompilers())
defineOption('native.libs', [])
defineOption('native.libpaths', [])
defineOption('native.c.flags', None) # defaults to native.cxx.flags if not set
defineOption('native.cxx.flags', [])
defineOption('native.cxx.path', [])
defineOption('native.include', [])
defineOption('native.link.flags', [])

if isWindows():
	defineOption('native.cxx.exenamefn', FilenameStringFormatter("%s.exe"))
	defineOption('native.cxx.libnamefn', FilenameStringFormatter("%s.dll"))
	defineOption('native.cxx.staticlibnamefn', FilenameStringFormatter("%s.lib"))
	defineOption('native.cxx.objnamefn', FilenameStringFormatter("%s.obj"))
else:
	defineOption('native.cxx.exenamefn', FilenameStringFormatter("%s"))
	defineOption('native.cxx.libnamefn', FilenameStringFormatter("lib%s.so"))
	defineOption('native.cxx.staticlibnamefn', FilenameStringFormatter("lib%s.a"))
	defineOption('native.cxx.objnamefn', FilenameStringFormatter("%s.o"))

class CompilerMakeDependsPathSet(BasePathSet):
	"""
		Use the selection ToolChain to get a list of dependencies from a set of source files
	"""
	def __init__(self, target, src, flags=None, includes=None):
		"""
		target -- the BaseTarget object for which this path set is being caculated

		src -- a PathSet of source file paths

		flags -- additional compiler flags

		includes -- a list of include directory paths
		"""
		self.target = target
		self.sources = src
		self.flags = flatten([flags]) or []
		self.includes = includes or []
	def __repr__(self):
		return "MakeDepend(%s, %s)" % (self.sources, self.flags)
	def resolveWithDestinations(self, context):
		return [(i, os.path.basename(i)) for i in _resolveUnderlyingDependencies(context)]
	def clean(self):
		dfile = self.target.workDir+'.makedepend'
		log = logging.getLogger('MakeDepend')
		deleteFile(dfile)
	def _resolveUnderlyingDependencies(self, context):
		deplist = None
		options = context.mergeOptions(self.target) # get the merged options
		log = logging.getLogger('MakeDepend')

		dfile = normLongPath(self.target.workDir+'.makedepend')
		testsources = self.sources.resolve(context)
		depsources = self.sources._resolveUnderlyingDependencies(context)

		needsRebuild = not os.path.exists(dfile)
		if needsRebuild:
			log.info("Rebuilding dependencies for %s because cached dependencies file does not exist (%s)" % (self.target, dfile))
		dfiletime = 0 if needsRebuild else getmtime(dfile) 
		for x in testsources:
			if not os.path.exists(x):
				return depsources
			elif getmtime(x) > dfiletime:
				if not needsRebuild:	log.info("Rebuilding dependencies for %s because cached dependencies file is older than %s" % (self.target, x))
				needsRebuild = True

		if not needsRebuild: # read in cached dependencies
			deplist = []
			with open(dfile) as f:
				lines = f.readlines()
				header = lines[0].strip()
				lines = lines[1:]
				for d in lines:
					d = d.strip()
					if context._isValidTarget(d) or exists(normLongPath(d)):
						deplist.append(d)
					else:
						needsRebuild = True
						log.warn("Rebuilding dependencies for %s because dependency %s is missing" % (self.target, d))
						break
			if header != str(self):
				log.info("Rebuilding dependencies for %s because target options have changed (%s != %s)" % (self.target, header, str(self)))
			elif not needsRebuild:
				return deplist

		# generate them again
		startt = time.time()
		log.critical("*** Generating dependencies for %s" % self.target)
		deplist = options['native.compilers'].dependencies.depends(context=context, src=testsources, options=options, flags=flatten(options['native.cxx.flags']+[context.expandPropertyValues(x).split(' ') for x in self.flags]), includes=flatten(self.includes.resolve(context)+[context.expandPropertyValues(x, expandList=True) for x in options['native.include']]))
		deplist += depsources
		mkdir(os.path.dirname(dfile))
		with openForWrite(dfile, 'wb') as f:
			assert not os.linesep in str(self)
			f.write(str(self)+os.linesep)
			for d in deplist:
				f.write(d.encode('UTF-8')+os.linesep)
		if time.time()-startt > 5: # this should usually be pretty quick, so may indicate a real build file mistake
			log.warn('Dependency generation took a long time: %0.1f s to evaluate %s', time.time()-startt, self)

		return deplist

class Cpp(BaseTarget):
	""" A target that compiles a C++ source file to a .o
	"""
	
	def __init__(self, object, source, includes=None, flags=None, dependencies=None, options=None):
		"""
		object -- the object file to generate
		source -- a (list of) source files
		includes -- a (list of) include directories
		flags -- a list of additional compiler flags
		dependencies -- a list of additional dependencies that need to be built 
		before this target
		"""
		self.source = PathSet(source)
		self.includes = PathSet(includes or []) 
		self.flags = flatten([flags]) or []
		self.options = options or {}
		self.makedepend = CompilerMakeDependsPathSet(self, self.source, flags=self.flags, includes=self.includes)
		BaseTarget.__init__(self, object, [dependencies or [], self.source, self.makedepend])
		self.tags('native')
	
	def run(self, context):
		options = context.mergeOptions(self) # get the merged options

		mkdir(os.path.dirname(self.path))
		options['native.compilers'].cxxcompiler.compile(context, output=self.path, options=options, flags=flatten(options['native.cxx.flags']+[context.expandPropertyValues(x).split(' ') for x in self.flags]), src=self.source.resolve(context), includes=flatten(self.includes.resolve(context)+[context.expandPropertyValues(x, expandList=True) for x in options['native.include']]))

	def clean(self, context):
		self.makedepend.clean()
		BaseTarget.clean(self, context)

	def getHashableImplicitInputs(self, context):
		r = super(Cpp, self).getHashableImplicitInputs(context)
		
		# include input to makedepends, since even without running makedepends 
		# we know we're out of date if inputs have changed
		r.append('depends: '+context.expandPropertyValues(str(self.makedepend)))
		
		return r
		
class C(BaseTarget):
	""" A target that compiles a C source file to a .o
	"""
	
	def __init__(self, object, source, includes=None, flags=None, options=None, dependencies=None):
		"""
		object -- the object file to generate
		source -- a (list of) source files
		includes -- a (list of) include directories
		flags -- a list of additional compiler flags
		dependencies -- a list of additional dependencies that need to be built 
		before this target
		"""
		self.source = PathSet(source)
		self.includes = PathSet(includes or []) 
		self.flags = flags or []
		self.makedepend = CompilerMakeDependsPathSet(self, self.source, flags=self.flags, includes=self.includes)
		BaseTarget.__init__(self, object, [dependencies or [], self.makedepend])
		self.options = options or {}
		self.tags('native')
	
	def run(self, context):
		options = context.mergeOptions(self) # get the merged options

		mkdir(os.path.dirname(self.path))
		options['native.compilers'].ccompiler.compile(context, output=self.path,
				options=options, 
				flags=flatten((options['native.c.flags'] or options['native.cxx.flags'])+[context.expandPropertyValues(x).split(' ') for x in self.flags]), 
				src=self.source.resolve(context),
				includes=flatten(self.includes.resolve(context)+[context.expandPropertyValues(x, expandList=True) for x in options['native.include']]))

	def clean(self, context):
		self.makedepend.clean()
		BaseTarget.clean(self, context)

	def getHashableImplicitInputs(self, context):
		r = super(C, self).getHashableImplicitInputs(context)
		
		# include input to makedepends, since even without running makedepends 
		# we know we're out of date if inputs have changed
		r.append(context.expandPropertyValues(str(self.makedepend)))
		
		return r
		
class Link(BaseTarget):
	""" A target that links object files to binaries
	"""
	
	def __init__(self, bin, objects, libs=None, libpaths=None, shared=False, options=None, flags=None, dependencies=None):
		"""
		bin -- the output binary

		objects -- a (list of) input object

		libs -- a (list of) libraries linked against (optional) in platform-neutral format. 
			Can include list properties like '${FOO_LIB_NAMES[]}'. 

		libpaths -- a (list of) additional library search directories (optional)

		shared -- if true compiles to a shared object (.dll or .so) (optional, defaults to false)

		flags -- a list of additional linker flags

		options -- a map of options to the underlying operation specific to this target (optional)

		dependencies -- a list of additional dependencies (targets or files)
		"""
		self.objects = PathSet(objects)
		self.libs = libs or []
		self.libpaths = PathSet(libpaths or [])
		self.shared=shared
		self.options = options
		self.flags = flags or []
		BaseTarget.__init__(self, bin, PathSet(self.objects, (dependencies or [])))
		self.tags('native')
	
	def run(self, context):
		options = context.mergeOptions(self) # get the merged options

		mkdir(os.path.dirname(self.path))
		options['native.compilers'].linker.link(context, output=self.path,
				options=options, 
				flags=options['native.link.flags']+self.flags, 
				shared=self.shared,
				src=self.objects.resolve(context),
				libs=flatten([map(string.strip, context.expandPropertyValues(x, expandList=True)) for x in self.libs+options['native.libs'] if x]),
				libdirs=flatten(self.libpaths.resolve(context)+[context.expandPropertyValues(x, expandList=True) for x in options['native.libpaths']]))

	def getHashableImplicitInputs(self, context):
		r = super(Link, self).getHashableImplicitInputs(context)
		
		options = context.mergeOptions(self)
		r.append('libs: '+context.expandPropertyValues(str(self.libs+options['native.libs'])))
		r.append('libpaths: '+context.expandPropertyValues(str(self.libpaths)))
		r.append('native.libpaths: %s'%options['native.libpaths'])
		r.append('shared: %s, flags=%s'%(self.shared, self.flags))
		
		return r
		
class Ar(BaseTarget):
	""" A target that compiles .a files from collections of .o files
	"""
	
	def __init__(self, bin, objects):
		"""
		bin -- the output library

		objects -- a (list of) input objects

		"""
		self.objects = PathSet(objects)
		BaseTarget.__init__(self, bin, self.objects)
		self.tags('native')
	
	def run(self, context):
		options = context.mergeOptions(self) # get the merged options

		mkdir(os.path.dirname(self.path))
		options['native.compilers'].archiver.archive(context, output=self.path,
				options=options,
				src=self.objects.resolve(context))

	def getHashableImplicitInputs(self, context):
		r = super(Ar, self).getHashableImplicitInputs(context)
		
		r.append('objects: %s'%self.objects)
		
		return r
		
exename = make_functor(lambda c, i:c.mergeOptions()['native.cxx.exenamefn'](c.expandPropertyValues(i)), name='exename')
objectname = make_functor(lambda c, i:c.mergeOptions()['native.cxx.objnamefn'](c.expandPropertyValues(i)), name='objectname')
libname = make_functor(lambda c, i:c.mergeOptions()['native.cxx.libnamefn'](c.expandPropertyValues(i)), name='libname')
staticlibname = make_functor(lambda c, i:c.mergeOptions()['native.cxx.staticlibnamefn'](c.expandPropertyValues(i)), name='staticlibname')

