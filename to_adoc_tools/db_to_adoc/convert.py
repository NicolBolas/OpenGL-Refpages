

import os
import pathlib
import re
import subprocess
from lxml import etree


def _replace_element_text(node, new_text):
    """Replaces the given element entirely with a piece of text."""
    
    #Get our tail text.
    tail = node.tail
    if tail == None:
        tail = ""
    
    #If there is a previous sibling node, then we need to add our
    #text and tail to the tail of the sibling.
    previous_node = node.getprevious()
    if previous_node is not None:
        prev_tail = previous_node.tail
        if prev_tail == None:
            prev_tail = ""
        
        previous_node.tail = prev_tail + new_text + tail
    else:
        #No previous, so add our text+tail to the text of the parent.
        parent_node = node.getparent()
        par_text = parent_node.text
        if par_text == None:
            par_text = ""
        parent_node.text = par_text + new_text + tail
    
    node.getparent().remove(node)


def _retag_element_text(node, prefix, suffix):
    """Given an XML element, replace the XML element markup,
    such that the text inside of the element is prefixed and suffixed
    with the given text."""
    our_text = "".join(node.itertext(with_tail=False))
    _replace_element_text(node, prefix + our_text + suffix)
    

def _remove_element(node, preserve_text = False):
    """Removes the given XML element. If `preserve_text` is True,
    the element's interior text will be preserved."""
    
    our_text = ""
    if preserve_text:
        our_text = "".join(node.itertext(with_tail=False))
    _replace_element_text(node, our_text)


_namespaces = {
'db' : 'http://docbook.org/ns/docbook',
'xi' : 'http://www.w3.org/2001/XInclude',
'xml' : 'http://www.w3.org/XML/1998/namespace',
}

def _xpath(xpath):
    return etree.XPath(xpath, namespaces=_namespaces)

_xpath_citations = _xpath("descendant::db:citerefentry")

_xpath_seealso = _xpath("descendant::*[@xml:id = 'seealso']")
_xpath_versions = _xpath("descendant::*[@xml:id = 'versions']")
_xpath_synopsis = _xpath("descendant::db:refsynopsisdiv")

_xpath_version_func_names = _xpath("descendant::db:row/db:entry")
_xpath_version_func_xptr = _xpath("descendant::db:row/xi:include/@xpointer")
_xpath_text = _xpath("descendant::text()")

_re_version_number = re.compile(r"\@role\=\'(.+)\'")


def _db(text):
    return "{http://docbook.org/ns/docbook}" + text


def _replace_seealso(seealso_node):
    """Replaces the 'seealso' section with a searchable replacement."""
    new_seealso = etree.Element(seealso_node.tag)
    new_seealso.set("{http://www.w3.org/XML/1998/namespace}id", "seealso")
    new_seealso.tail = seealso_node.tail
    
    new_title = etree.SubElement(new_seealso, _db("title"))
    new_title.text = "See Also"
    new_title.tail = "\n\t\t"
    
    new_para = etree.SubElement(new_seealso, _db("para"))
    new_para.text = "SEEALSO_TEXT_REPLACEMENT"
    new_para.tail = "\n\t"
    
    parent = seealso_node.getparent()
    parent.replace(seealso_node, new_seealso)


def _parse_version_from_xpointer(main_file, xptr):
    ver = _re_version_number.search(xptr)
    if ver:
        #TODO: if main_file is GLSL, then the version needs to have a `0`
        #added to the end.
        return ver.groups(1)[0]

    return xptr


def _replace_versions(xml_root, main_file):
    """Replaces all version elements with a text parsable list
    of versions."""
    versions = _xpath_versions(xml_root)

    if len(versions) == 0:
        return

    for version_node in versions:
        new_version = etree.Element(version_node.tag)
        new_version.set("{http://www.w3.org/XML/1998/namespace}id", "versions")
        new_version.tail = version_node.tail

        new_title = etree.SubElement(new_version, _db("title"))
        new_title.text = "Versions"
        new_title.tail = "\n\t\t"
        
        start_para = etree.SubElement(new_version, _db("para"))
        start_para.text = "VERSION_START_DELIMETER"
        start_para.tail = "\n\t\t"
        
        funcs = ["".join(_xpath_text(entry))
            for entry in _xpath_version_func_names(version_node)]
        xptrs = [_parse_version_from_xpointer(main_file, xptr)
            for xptr in _xpath_version_func_xptr(version_node)]
            
        for func, xptr in zip(funcs, xptrs):
            version_elem = etree.SubElement(new_version, _db("para"))
            version_elem.text = F"VERSION OF '{func}' FOR '{xptr}'"
            version_elem.tail = "\n\t\t"

        end_para = etree.SubElement(new_version, _db("para"))
        end_para.text = "VERSION_END_DELIMETER"
        end_para.tail = "\n\t"
        
        version_node.getparent().replace(version_node, new_version)


def _replace_synopsis(xml_root):
    """Replaces the DocBook function synopsis with a section that we will write our synopsis into later."""

    synopsis_node = _xpath_synopsis(xml_root)[0]

    new_synopsis = etree.Element(_db("refsect1"))
    new_synopsis.tail = synopsis_node.tail

    new_title = etree.SubElement(new_synopsis, _db("title"))
    new_title.text = "Functions"
    new_title.tail = "\n\t\t"

    new_para = etree.SubElement(new_synopsis, _db("para"))
    new_para.text = "FUNCSYNOPSIS_TEXT_REPLACEMENT"
    new_para.tail = "\n\t"

    synopsis_node.getparent().replace(synopsis_node, new_synopsis)


def transform_docbook(dest_dir, main_file):
    """Creates a temporary copy of the DocBook file, containing
    modifications meant to make it easy to do post-Pandoc cleanup tasks.
    Returns the path to the temporary directory."""
    xml_root = main_file.copy_xml()

    #Replace sysnopsis
    _replace_synopsis(xml_root)

    #Replace SeeAlso nodes.
    #Make sure that the XPath is completely finished before
    #messing with the XML
    for node in [node for node in _xpath_seealso(xml_root)]:
        _replace_seealso(node)
    
    #Replace version nodes.
    _replace_versions(xml_root, main_file)
    
    #Remove citations.
    #TODO: Make this generate AsciiDoc text for actual inter-page citations
    citations = [node for node in _xpath_citations(xml_root)]
    
    for citation in citations:
        _remove_element(citation, preserve_text=True)

    #Write file.
    dest_file = dest_dir / (main_file.name() + ".xml")
    xml_tree = etree.ElementTree(xml_root)
    xml_tree.write(str(dest_file), encoding="UTF-8", xml_declaration=True)
    
    return dest_file


def to_asciidoctor(dest_dir, source_path):
    """Performs Pandoc conversion of source to destination.
    Returns the path to the generated file."""
    dest_file = dest_dir / (source_path.stem + ".adoc")

    cmdline = F'pandoc -o "{dest_file}" --from=docbook --to=asciidoc "{source_path}"'
    #print(cmdline)
    ret = subprocess.run(cmdline)

    return dest_file

def to_final_asciidoctor(dest_dir, source_path):
    """Does various textual fixups within the AsciiDoctor files. Writes the 
    data to the given directory. Returns the path of the generated file."""
    pass


_adoc_cmd = 'asciidoctor -d article -o {dest} -b html5 {src}'
#_adoc_cmd = 'asciidoctor'

def to_html(dest_dir, source_path):
    """Performs AsciiDoctor conversion from AsciiDoc to HTML, into the given directory.
    Returns path to the generated file."""
    dest_file = dest_dir / (source_path.stem + ".html")

    cmdline = _adoc_cmd.format(dest = dest_file, src = source_path)
    print(cmdline)
    ret = subprocess.run(cmdline, shell=True)

    return dest_file


