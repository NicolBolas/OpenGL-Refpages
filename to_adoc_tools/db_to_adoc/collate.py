
import os
import pathlib
import re
from lxml import etree

_namespaces = {
'db' : 'http://docbook.org/ns/docbook',
'xi' : 'http://www.w3.org/2001/XInclude',
}

#Useful XPaths. Don't need to recreate them a bunch.
_xpath_header_abstract_text = etree.XPath("db:refnamediv/db:refpurpose/descendant::text()", namespaces=_namespaces)
_xpath_header_function_names = etree.XPath("db:refsynopsisdiv/db:funcsynopsis/db:funcprototype/db:funcdef/db:function/text()", namespaces=_namespaces)

_xpath_function = etree.XPath("db:refsynopsisdiv/db:funcsynopsis/db:funcprototype", namespaces=_namespaces)

_xpath_func_name_prototype_text = etree.XPath("db:funcdef/db:function/text()", namespaces=_namespaces)

_xpath_func_def_prototype = etree.XPath("db:funcdef", namespaces=_namespaces)
_xpath_func_parameters = etree.XPath("db:paramdef", namespaces=_namespaces)
_xpath_func_paramname = etree.XPath("db:parameter", namespaces=_namespaces)

_xpath_citations = etree.XPath("descendant::db:citerefentry", namespaces=_namespaces)
_xpath_citation_target = etree.XPath("db:refentrytitle/text()", namespaces=_namespaces)

_xpath_xincludes = etree.XPath("descendant::xi:include", namespaces=_namespaces)

#Useful regexes.
_re_line_end = re.compile("\n\s*")
_re_name_array = re.compile(r"(.+)(\[.+\])")

"""The names of includes that should be ignored."""
ignored_includes = {
    "apiversion.xml": True,
    "apifunchead.xml": True,
    "funchead.xml": True,
    "version.xml": True,
    "varhead.xml": True,
}



class FuncDecl:
    """Specifies a function name, return value, and a list of
    parameter names & types."""
    
    def _parse_parameter(paramdef):
        """Generates a dictionary containing the parameter name
        and its type."""
        
        #Process type
        type = paramdef.text
        
        if type == None:
            #print("\t'void'")
            return {"type": "void"}

        type = type.strip()
        optional = False
        
        #Parameter is optional if it starts with a `[`.
        if type.startswith("["):
            type = type[1:]
            optional = True
        
        #Process name.
        name_node = _xpath_func_paramname(paramdef)
        name = None
        
        if len(name_node) == 0:
            #print("UNNAMED PARAM")
            name = ""
        else:
            name = name_node[0].text
            name = name.strip()

            #Sometimes, a name ends in a `[#]`, which is part of the type.
            match = _re_name_array.match(name)
            if match:
                groups = match.group(1, 2)
                name = groups[0]
                type = type + groups[1]
            
            #Sometimes, an optional parameter puts the `]` after
            #the name text instead of after `<parameter>`
            if name.endswith("]"):
                name = name[:-1]
                

        #if optional:
        #    print(F"\t'{type}', '{name}', 'optional'")
        #else:
        #    print(F"\t'{type}', '{name}'")
        
        return {"type": type, "name": name, "optional": optional}

    
    def __init__(self, funcprototype):
        """Extracts the name/return value & parameter list data from
        a DocBook `funcprototype` element"""
        self._name = "".join(_xpath_func_name_prototype_text(funcprototype))
        self._name = self._name.strip()

        func_node = _xpath_func_def_prototype(funcprototype)
        self._return_value = func_node[0].text
        self._return_value = self._return_value.strip()
        
        #print(F"{self._name} '{self._return_value}'")
        
        self._params = [FuncDecl._parse_parameter(param)
            for param in _xpath_func_parameters(funcprototype)]
        

    def name(self):
        return self._name


class MainFile:
    """Contains the data for a file to be processed."""
    
    def __init__(self, file_path, xml_root):
        """Processes the XML to generate the appropriate data
        for the file."""
        self._file_path = file_path
        
        if xml_root.tag == '{http://docbook.org/ns/docbook}refentry':
            self._adoc_path = F"{file_path.stem}.adoc"
            if file_path.stem.startswith("gl_"):
                self._type = "glsl_var"
            elif file_path.stem.startswith("gl"):
                self._type = "gl_func"
            else:
                self._type = "glsl_func"

            self._process_header(xml_root)
            self._process_functions(xml_root)
        else:
            self._type = "included"
            self._adoc_path = F"_inc_{file_path.stem}.adoc"
        
        #print(self._type, file_path.stem)
        
        self._process_citations(xml_root)
        self._process_includes(xml_root)


    def _process_header(self, xml_root):
        """Extracts the function names and abstract."""
        try:
            abstract_text = _xpath_header_abstract_text(xml_root)
            if len(abstract_text) == 0:
                print(F"{self._file_path} ERROR: No abstract header.")
                return

            abstract_text = "".join(abstract_text)
            
            #Remove any `\n`s followed by spaces.
            abstract_text = re.sub(_re_line_end, " ", abstract_text)
            
            self._abstract_text = abstract_text
            
            func_names = _xpath_header_function_names(xml_root)
            if len(func_names) > 0:
                #Remove duplicate names, but don't sort them.
                func_names = list(dict.fromkeys(func_names))

                self._hdr_func_names = func_names
            else:
                self._hdr_func_names = None
            
            #print(self._abstract_text)
            #print(self._hdr_func_names)

        except etree.XPathError as e:
            print(F"{self._file_path} ERROR: {e}")


    def _process_functions(self, xml_root):
        """Reads the `refsynopsisdiv` and builds sufficient
        information to generate Asciidoc text for them. But
        don't build that text here."""
        self._funcs = [FuncDecl(node) for node in _xpath_function(xml_root)]


    def _process_citation(node):
        """Processes a single citation, returning the target."""
        cite_target = _xpath_citation_target(node)
        cite_target = ";".join(cite_target)
        #print(cite_target)
        return cite_target


    def _process_citations(self, xml_root):
        """Finds all `citerefentry` entries and builds a list of
        both their text and what they link to."""
        self._citations = [MainFile._process_citation(node)
            for node in _xpath_citations(xml_root)]


    def _process_include(node):
        #print(F"{'href' in node.attrib}, {'xpointer' in node.attrib}")
        include = node.attrib['href']
        #print(include)
        return include
    

    def _process_includes(self, xml_root):
        """Finds `xi:include` elements and builds a list of these
        target files."""
        self._includes = [MainFile._process_include(node)
            for node in _xpath_xincludes(xml_root)
            if node.attrib["href"] not in ignored_includes]


    def type(self):
        """Retrieves the basic kind of this file."""
        return self._type
        

    def path(self):
        """Retrieves the path name of the source file"""
        return self._file_path


    def dest_file(self):
        """Retrieves the destination filename."""
        return self._adoc_path
    
    
    def name(self):
        """The base name of the source file"""
        return self._file_path.stem
        

    def abstract_text(self):
        """Retrieves the textual abstract."""
        return self._abstract_text
    
    
    def func_names_unique(self):
        """Retrieves a list of unique functions defined by this file."""
        return self._hdr_func_names


class Collate:
    """Reads a given directory and generates data about the
    DocBook XML files within."""
    
    def __init__(self, doc_dir_path):
        """Searches the given directory for XML files and processes
        them into two sets: Files the aren't included and files
        that are included."""
        
        doc_dir_path = pathlib.PurePath(doc_dir_path)
        
        self._included_files = []
        self._main_files = []
        
        self._all_files = [self._collate_docbook(doc_dir_path / dir_entry.name)
            for dir_entry in os.scandir(doc_dir_path)
            if dir_entry.is_file()
            if dir_entry.name.lower().endswith(".xml")
            if dir_entry.name not in ignored_includes]
        
        self._all_dict = {file.name : file
            for file in self._all_files}
        
        types = set()
        for file in self._all_files:
            types.add(file.type())
        
        self._by_type = {type : {file.name : file
                for file in self._all_files
                if file.type() == type}
            for type in types}
        
        print(types, len(self._by_type))
        
        for type, type_dict in self._by_type.items():
            print(type, len(type_dict))
        
        print(F"Total: {len(self._all_files)}")


    def _collate_docbook(self, file_path):
        """Parses XML file and figures out if it is a refentry or not.
        Performs different processing depending on which it is."""
        
        try:
            tree = etree.parse(str(file_path))
            root = tree.getroot()
            
            return MainFile(file_path, root)
            
        except etree.XMLSyntaxError as e:
            print(F"File: {file_path} ERROR: {e}")

        
    
    def _add_include(self, file_path, root):
        """Adds the file as an inclusion file."""
        #TODO
        pass


