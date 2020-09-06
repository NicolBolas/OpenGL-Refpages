
import os
import pathlib
from lxml import etree

_xpath_refnamediv = etree.ETXPath("descendant::{http://docbook.org/ns/docbook}refnamediv")
_xpath_refname_text = etree.ETXPath("{http://docbook.org/ns/docbook}refname/text()")
_xpath_refpurpose_text = etree.ETXPath("{http://docbook.org/ns/docbook}refpurpose/descendant::text()")


class MainFile:
    """Contains the data for a main file to be processed."""
    
    def __init__(self, file_path, xml_root):
        """Processes the XML to generate the appropriate data
        for the main file."""
        self._file_path = file_path
        self._adoc_path = F"{file_path.stem}.adoc"
        
        self._process_header(xml_root)
        self._process_functions(xml_root)
        self._process_citations(xml_root)
        self._process_includes(xml_root)


    def _process_header(self, xml_root):
        """Reads the `refnamediv` and builds adoc string for the header"""
        try:
            refnamediv = _xpath_refnamediv(xml_root)
            if len(refnamediv) == 0:
                print(F"{self._file_path} ERROR: {e}")
                return
            
            refname = _xpath_refname_text(refnamediv[0])
            refpurpose = _xpath_refpurpose_text(refnamediv[0])
            refpurpose = "".join(refpurpose)
            print(refpurpose)
            
        except etree.XPathError as e:
            print(F"{self._file_path} ERROR: {e}")


    def _process_functions(self, xml_root):
        """Reads the `refsynopsisdiv` and builds appropriate information
        about the functions the file defines."""
        pass


    def _process_citations(self, xml_root):
        """Finds all `citerefentry` entries and builds a list of
        both their text and what they link to."""
        self._citations = []


    def _process_includes(self, xml_root):
        """Finds `xi:include` elements and builds a list of these
        target files."""
        pass


    def path(self):
        """Retrieves the path name"""
        return self._file_path


    def dest_file(self):
        """Retrieves the destination filename."""
        return self._adoc_path


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
        
        with os.scandir(doc_dir_path) as dirIt:
            for dir_entry in dirIt:
                if(dir_entry.is_file()):
                    file_path = doc_dir_path / dir_entry.name
                    if file_path.suffix.lower() == ".xml":
                        self._collate_docbook(file_path)


    def _collate_docbook(self, file_path):
        """Parses XML file and figures out if it is a refentry or not.
        Performs different processing depending on which it is."""
        
        try:
            tree = etree.parse(str(file_path))
            root = tree.getroot()
            
            if root.tag == '{http://docbook.org/ns/docbook}refentry':
                data = MainFile(file_path, root)
                self._main_files.append(data)
            else:
                self._add_include(file_path, root)

        except etree.XMLSyntaxError as e:
            print(F"File: {file_path} ERROR: {e}")

        
    
    def _add_include(self, file_path, root):
        """Adds the file as an inclusion file."""
        pass


