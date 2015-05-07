"""
CliMAF macros module :

- define macros from CliMAF objects,
- find macro patterns in CRS expressions,
- rewrite CRS expressions,
- read/write macro set

"""

import sys, os

from classes import cobject, cdataset, ctree, scriptChild, cpage
from clogging import clogger, dedent

#: Dictionnary of macros
cmacros=dict()

#: Filename for storing macros
macroFilename="~/.climaf.macros"

class cdummy(cobject):
    def __init__(self):
        """
        cdummy class represents dummy arguments in the CRS
        """
        pass
    def buildcrs(self,period=None,crsrewrite=None):
        return('ARG')

def cmacro(name,cobj,lobjects=[]):
    """

    Define a CliMAF macro from a CliMAF compound object.

    Transform a Climaf object in a macro, replacing all datasets,
    and the objects of lobjects, by a dummy argument.  Register it in
    dict cmacros, if name is not None

    Args:
     name (string) : the name you want to give to the macro; a Python
      function with the same name will be defined
     cobj (CliMAF object, or string) : any CliMAF object, usually
      the result of a series of operators, that you would like to
      repeat using other input datasets; alternatively, you can provide
      the macro formula as a string (when accustomed to the syntax)
     lobjects (list, optional):  for expert use- a list of objects,
      which are sub-objects of cobject, and which should become arguments
      of the macro

    Returns:
      a macro; the returned value is usualy not used asis; a python
      function is also defined in module cmacros, and you may import it
      and use it in the same way as a CliMAF operator. All the datasets
      involved in ``cobj`` become arguments of the macro, which
      allows you to re-do the same computations and easily define
      objects similar to ``cobjs``

    Example::

     >>> # First use and combine CliMAF operators to get some interesting result using some dataset(s)
     >>> january_ta=ds(project='example',experiment='AMIPV6ALB2G',variable='ta',frequency='monthly',period='198001')
     >>> ta_europe=llbox(january_ta,latmin=40,latmax=60,lonmin=-15,lonmax=25)
     >>> ta_ezm=ccdo(ta_europe,operator='zonmean')
     >>> fig_ezm=plotxsec(ta_ezm)
     >>> #
     >>> # Using this result as an example, define a macro named 'eu_cross_section',
     >>> # which arguments will be the datasets involved in this result
     >>> cmacro('eu_cross_section',fig_ezm)
     >>> #
     >>> # You can of course apply a macro to other dataset(s), 
     >>> pr=ds(project='example',experiment='AMIPV6ALB2G', variable='pr', frequency='monthly', period='198001')
     >>> pr_ezm=climaf.cmacros.eu_zonal_mean(pr)
     >>> #
     >>> # A simpler way to use it ; first import the macro
     >>> from climaf.cmacros import eu_zonal_mean
     >>> # or :
     >>> from climaf.cmacros import *
     >>> pr_ezm=eu_zonal_mean(pr)
     >>> #
     >>> # All macros are registered in dictionnary climaf.cmacros.cmacros,
     >>> # which is imported by climaf.api; you can list it by :
     >>> cmacros


    See also much more explanations in the example at :download:`macro.py <../examples/macro.py>`
    """
    if isinstance(cobj,str) :
        # Next line used for interpreting macros's CRS
        exec("ARG=climaf.cmacros.cdummy()", sys.modules['__main__'].__dict__)
        cobj=eval(cobj, sys.modules['__main__'].__dict__)
    domatch=False
    for o in lobjects :
        domatch = domatch or cobj==o or \
                  ( isinstance(cobj,cobject) and cobj.buildcrs() == o.buildcrs())
    if isinstance(cobj,cdataset) or isinstance(cobj,cdummy) or domatch :
        return cdummy()
    elif isinstance(cobj,ctree) :
        rep=ctree(cobj.operator, cobj.script,
                  *cobj.operands, **cobj.parameters)
        rep.operands = map(cmacro,[ None for o in rep.operands],rep.operands)
    elif isinstance(cobj,scriptChild) :
        rep=scriptChild(cmacro(None,cobj.father),cobj.varname)
    elif isinstance(cobj,cpage) :
        rep=cpage(cobj.widths_list, cobj.heights_list,
                  [ map(cmacro, [ None for fig in line ], line) for line in cobj.fig_lines ] ,
                  cobj.orientation)
    elif cobj is None : return None
    else :
        clogger.error("Cannot yet handle object :%s", `cobj`)
        rep=None
    if name and rep :
        cmacros[name]=rep
        doc="A CliMAF macro, which text is "+`rep`
        defs='def %s(*args) :\n  """%s"""\n  return instantiate(cmacros["%s"],[ x for x in args])\n'\
              % (name,doc,name)
        exec defs in globals() 
        clogger.debug("Macro %s has been declared"%name)

    return rep


def crewrite(crs,alsoAtTop=True):
    """
    Return the crs expression with sub-trees replaced by macro equivalent 
    when applicable

    Search order is : from CRS tree root try all macros, then do the
    same for first subtree, and recursively in depth, and then go 
    to second subtreesecond 
    """
    # Next line used for interpreting macros's CRS
    exec("ARG=climaf.cmacros.cdummy()", sys.modules['__main__'].__dict__)
    #
    co=eval(crs, sys.modules['__main__'].__dict__)
    if isinstance(co,ctree) or isinstance(co,scriptChild) or isinstance(co,cpage) :
        if alsoAtTop :
            for m in cmacros :
                clogger.debug("looking at macro : "+m+"="+`cmacros[m]`+\
                           " \ncompared to : "+`cmacro(None,co)`)
                argl=cmatch(cmacros[m],co)
                if len(argl) > 0 :
                    rep=m+"("
                    for arg in argl :
                        rep+=crewrite(arg.buildcrs(crsrewrite=crewrite))+","
                    rep+=")"; rep=rep.replace(",)",")")
                    return rep
        # No macro matches at top level, or top level not wished.
        # Let us dig a bit
        return(co.buildcrs(crsrewrite=crewrite))
    else :
        return(crs)

def cmatch(macro,cobj) :
    """
    Analyze if macro does match cobj, and return the list of objects
    matching macro arguments, ordered by depth-first traversal
    """
    clogger.debug("matching "+`macro`+" and "+`cobj`)
    if isinstance(cobj,ctree) and isinstance(macro,ctree) and \
           macro.operator==cobj.operator :
        nok=False
        for mpara,para in zip(macro.parameters,cobj.parameters) :
            if mpara != para or \
                   macro.parameters[para] != cobj.parameters[para]:
                nok=True
        if nok : return []
        argsub=[]
        for mop,op in zip(macro.operands,cobj.operands) :
            if isinstance(mop,cdummy) :
                argsub.append(op)
            else :
                argsub+=cmatch(mop,op)
        return(argsub)
    elif isinstance(cobj,scriptChild) and isinstance(macro,scriptChild) and \
           macro.varname==cobj.varname :
        return(cmatch(macro.father,cobj.father,argslist))
    else : return []
    
    
def read(filename=macroFilename):
    """
    Read macro dictionnary from filename, and add it to cmacros[]
    """
    import json
    global cmacros
    macros_texts=None
    try :
        macrofile=file(os.path.expanduser(filename), "r")
        clogger.debug("Macrofile %s read"%(macrofile))
        macros_texts=json.load(macrofile)
        clogger.debug("After reading file %s, macros=%s"%(macrofile,`macros_texts`))
        macrofile.close()
    except:
        clogger.info("Issue reading macro file %s ", filename)
    if macros_texts :
        for m in macros_texts :
            clogger.debug("loading macro %s"%m)
            cmacro(m,macros_texts[m])


def write(filename=macroFilename) :
    """
    Writes macros dictionnary to disk ; should be called before exit

    """
    import json
    filen=os.path.expanduser(filename)
    try :
        os.remove(filen)
    except :
        pass
    macrofile=file(filen, "w")
    dcrs=cmacros.copy()
    for m in dcrs : dcrs[m]=dcrs[m].buildcrs()
    json.dump(dcrs,macrofile,sort_keys=True,indent=4)
    macrofile.close()



def show(interp=True) :
    """
    List the macros, searching also for macro usage in macros (except if arg ``interp`` is True)
    """
    for m in cmacros :
        if interp :
            print "% 15s : %s"%(m,crewrite(cmacros[m].buildcrs(),alsoAtTop=False))
        else :
            print "% 15s : %s"%(m,cmacros[m])

def instantiate(mac,operands, toplevel=True) :
    """
    Return a copy of macro cobject ``mac`` where arguments are instantiated by the list
    `operands', used in the order of depth-first tree traversal of ``mac``.

    Check that the number of operands is OK vs mac
    """
    if isinstance(mac,cdummy) :
        if len(operands) > 0 :
            rep=operands.pop(0)
        else :
            raise Climaf_Macro_Error('no operand left')
    elif isinstance(mac,ctree) :
        opers=[]
        for o in mac.operands : opers.append(instantiate(o,operands,toplevel=False))
        rep=ctree(mac.operator,mac.script,*opers,**mac.parameters)
    elif isinstance(mac,scriptChild) :
        father=instantiate(mac.father,operands,toplevel=False)
        rep=scriptChild(father,mac.variable)
    elif isinstance(mac,cdataset) :
        rep=cdataset
    if toplevel and len(operands) != 0 :
        raise Climaf_Macro_Error('too many operands; left operands are : '+`operands`)
    return(rep)

class Climaf_Macro_Error(Exception):
    def __init__(self, valeur):
        self.valeur = valeur
        clogger.error(self.__str__())
        dedent(100)
    def __str__(self):
        return `self.valeur`

