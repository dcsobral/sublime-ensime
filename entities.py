from sexp_parser import sexp
from collections import defaultdict


    # def rootDir(): Option[String]
    # def useSbt(): Boolean
    # def useMaven(): Boolean
    # def useIvy(): Boolean
    # def sbtActiveSubproject(): Option[SbtSubproject]
    # def ivyRuntimeConf(): Option[String]
    # def ivyCompileConf(): Option[String]
    # def ivyTestConf(): Option[String]
    # def ivyFile(): Option[String]
    # def runtimeJars(): List[String]
    # def excludeRuntimeJars(): List[String]
    # def compileJars(): List[String]
    # def excludeCompileJars(): List[String]
    # def classDirs(): List[String]
    # def sources(): List[String]
    # def target(): Option[String]
    # def projectName(): Option[String]
    # def formatPrefs(): Map[Symbol, Any]
    # def disableIndexOnStartup(): Boolean
    # def excludeFromIndex(): List[Regex]

def swank_bool(bl):
  bl.lower() == 't'

class EnsimeProject:

  def __init__(self, path):
    self.values = self._read_values()
    self.root_dir = path

  def _read_values(self):
    ast = sexp.parseFile(path)[0]
    vals = [(v[1:], ast[i +1]) for i, v in enumerate(ast) if i % 2 == 0] 
    values = defaultdict()
    for k, vv in [(v[1:], ast[i +1]) for i, v in enumerate(ast) if i % 2 == 0]:
      values[k] = vv
    return values

  def use_sbt(self):
    swank_bool(self.values.get('use-sbt'))
