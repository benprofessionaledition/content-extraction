import logging
import re
from abc import ABC, abstractmethod

import math
from bs4 import BeautifulSoup, Tag
from math import log as ln

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

"""
A pure Python implementation of content extraction via composite text density. The overall 
idea of this algorithm is to detect which parts of a web page are relevant by comparing the "text 
density," which is a metric derived from the ratio of hyperlink to non-hyperlink characters, of 
all DOM nodes in the tree. Those DOM nodes determined to be relevant then have their text portions
included in the final output. 

Original paper: http://ofey.me/papers/cetd-sigir11.pdf
Original code: https://github.com/FeiSun/ContentExtraction
"""

KG_CHAR_NUM = 'char-number'
KG_TAG_NUM = 'tag-number'
KG_LINKCHAR_NUM = 'linkchar-number'
KG_LINKTAG_NUM = 'linktag-number'
KG_TEXT_DENSITY = 'text-density'
KG_DENSITY_SUM = 'density-sum'
KG_MAX_DENSITY_SUM = 'max-density-sum'
KG_MARK = 'mark'
KG_GEOMETRY = 'geometry'

LINK_TAGS = {'a', 'button', 'select'}
JS_TAGS = {'script', 'style'}

whitespace_regex = re.compile(r'(\s{2,}|\t)')


def first_child(web_element: Tag) -> Tag:
    for c in web_element.children:
        if isinstance(c, Tag):
            return c

def search_tag(web_element: Tag, attribute: str, value: float) -> Tag:
    """
    A method for returning the first occurrence of a Tag having the value specified
    for the attribute provided
    :param web_element:
    :param attribute:
    :param value:
    :return:
    """
    attribute = str(attribute)
    value = str(value)
    try:
        if web_element[attribute] == value:
            return web_element
    except KeyError:
        pass  # ignore
    kws = {attribute: value}
    target = web_element.find_next(**kws)
    if target is None:
        # find the next usable sibling and search it
        for sibling in web_element.descendants:
            if isinstance(sibling, Tag):
                target = search_tag(sibling, attribute, value)
                break
    return target


def is_ignorable(tag: Tag, ignorables: set = LINK_TAGS.union(JS_TAGS)) -> bool:
    """
    Returns true if the tag provided is considered ignorable for the current use case.
    By default this entails link text (like <a href=.../>) and javascript tags that
    we don't care about. In the original paper only link tags were included, but that
    was in 2011.
    :param tag:
    :return:
    """
    return tag.name.lower() in ignorables


def find_max_density_sum(web_element: Tag) -> float:
    """
    Finds the maximum density sum across all child nodes of the element
    provided
    :param web_element:
    :return:
    """
    try:
        max_density_sum = web_element[KG_DENSITY_SUM]
    except KeyError:
        max_density_sum = 0
    temp_max = 0
    for child in web_element.children:
        if isinstance(child, Tag):
            temp_max = find_max_density_sum(child)
        max_density_sum = max(temp_max, max_density_sum)
    web_element[KG_MAX_DENSITY_SUM] = max_density_sum
    return max_density_sum


def get_threshold(web_element: Tag, max_density_sum: float) -> float:
    target = search_tag(web_element, KG_DENSITY_SUM, max_density_sum)
    threshold = float(target[KG_TEXT_DENSITY])
    set_mark(target, 1)
    parent = target.parent
    while parent.name.lower() != 'html':
        text_density = float(parent[KG_TEXT_DENSITY])
        threshold = min(threshold,
                        text_density)  # i think... "if threshold - text_density > -1 * std::numeric_limits<double>::epsilon()" whatever the fuck that means
        parent[KG_MARK] = 2  # magic constant
        parent = parent.parent
    return threshold


def set_mark(web_element: Tag, mark: int):
    web_element[KG_MARK] = mark
    for child in web_element.children:
        if isinstance(child, Tag):
            set_mark(child, mark)


def mark_content(web_element: Tag, threshold: float):
    text_density = float(web_element[KG_TEXT_DENSITY])
    max_density_sum = float(web_element[KG_MAX_DENSITY_SUM])
    mark = int(web_element[KG_MARK])
    if mark != 1 and threshold > text_density:  # again, this is written a stupid way
        find_max_density_sum_tag(web_element, max_density_sum)
        if isinstance(web_element, Tag):
            for child in web_element.children:
                mark_content(child, threshold)


def find_max_density_sum_tag(web_element: Tag, max_density_sum: float):
    """
    Finds the tag having the max density sum and "marks" it for inclusion later
    :param web_element:
    :param max_density_sum:
    :return:
    """
    target = search_tag(web_element, KG_DENSITY_SUM, max_density_sum)
    mark = int(target[KG_MARK])
    if mark != 1:
        set_mark(target, 1)
        parent = target.parent
        while parent.name.lower() != 'html':
            parent[KG_MARK] = 2  # magic constant, again
            parent = parent.parent


class AbstractExtractor(ABC):
    """
    An abstract superclass encapsulating most of the functionality of
    the composite text density extraction algorithm, leaving a few methods
    open to variable implementations
    """
    def __init__(self, removables=JS_TAGS, ignorable_tags=LINK_TAGS.union(JS_TAGS)):
        """
        Initialize the abstract superclass by defining removable and ignorable tags
        :param removables: tags that will be removed entirely from the final output
        :param ignorable_tags: tags whose content will be weighted as undesirable content
        """
        self.removables = removables
        self.ignorable_tags = ignorable_tags

    def create_doc(self, html: str) -> Tag:
        return BeautifulSoup(html, 'html.parser').body

    def extract_content(self, html: str) -> str:
        bs = self.create_doc(html)
        self.preprocess_dom(bs)
        self.count_chars(bs)
        self.count_tags(bs)
        self.count_link_chars(bs)
        self.count_link_tags(bs)
        char_num = bs[KG_CHAR_NUM]
        linkchar_num = bs[KG_LINKCHAR_NUM]
        ratio = linkchar_num / char_num
        self.compute_text_density(bs, ratio)
        self.compute_density_sum(bs, ratio)
        logger.debug("Density sums: ")
        max_density_sum = find_max_density_sum(bs)
        # [logger.debug('Node name: %s \t Density sum: %f \t Max sum: %f' % (l.name, l[KG_DENSITY_SUM], max_density_sum))
        #  for l in bs.descendants if isinstance(l, Tag)]
        set_mark(bs, 0)
        threshold = get_threshold(bs, max_density_sum)
        mark_content(bs, threshold)
        # we don't actually care about cleaning the tree or returning DOM nodes
        kws = {KG_MARK: 0}
        zero_elements = bs.find_all(**kws)
        [z.extract() for z in zero_elements]
        output_dirty = bs.get_text()
        # remove excess whitespace and duplicate newline characters
        output_dirty = whitespace_regex.sub(' ', output_dirty)
        output = '\n'.join(list(filter(lambda s: len(s.strip()) > 0, output_dirty.splitlines())))
        return output

    @abstractmethod
    def count_chars(self, web_element: Tag):
        pass

    @abstractmethod
    def update_link_chars(self, web_element: Tag):
        pass

    @abstractmethod
    def compute_text_density(self, web_element: Tag, ratio: float):
        pass

    @abstractmethod
    def compute_density_sum(self, web_element: Tag, ratio: float):
        pass

    def preprocess_dom(self, web_element: Tag):
        """
        Removes all nodes with the "display" property set to "none"
        :param web_element:
        :return:
        """
        target_args = {"display": "none"}
        remove = web_element.find_all(**target_args) + web_element.find_all(*self.removables)
        [r.extract() for r in remove]
        # additionally remove js tags--not in original
        for sib in web_element.next_siblings:
            if isinstance(sib, Tag):
                self.preprocess_dom(sib)

    def count_tags(self, web_element: Tag):
        """
        Counts the number of tags in the children of the element provided
        :param web_element:
        :return: void
        """
        tag_num = 0
        if web_element.next_element is not None:
            for child in web_element.children:
                if isinstance(child, Tag):
                    self.count_tags(child)
            for child in web_element.children:
                if isinstance(child, Tag):
                    tag_num += child[KG_TAG_NUM]
        web_element[KG_TAG_NUM] = tag_num

    def count_link_chars(self, web_element: Tag):
        """
        Recursively counts all link characters in the children of the tag provided
        :param web_element:
        :return:
        """
        linkchar_num = 0
        for child in web_element.children:
            if isinstance(child, Tag):
                self.count_link_chars(child)
        if is_ignorable(web_element, self.ignorable_tags):
            linkchar_num = web_element[KG_CHAR_NUM]
            self.update_link_chars(web_element)
        else:
            for child in web_element.children:
                if isinstance(child, Tag):
                    linkchar_num += child[KG_LINKCHAR_NUM]
        web_element[KG_LINKCHAR_NUM] = linkchar_num

    def update_link_tags(self, web_element: Tag):
        """
        Recursively updates this tag and all its children with the number of
        link tags in the tree they're currently in.
        :param web_element:
        :return:
        """
        for child in web_element.children:
            if isinstance(child, Tag):
                child[KG_LINKTAG_NUM] = child[KG_TAG_NUM]
                self.update_link_tags(child)

    def count_link_tags(self, web_element: Tag):
        """
        Counts the number of child tags for the parameter that are "link" tags,
        i.e. the text they represent is hyperlinks or buttons. This signifies that we
        probably don't care about the text contained therein.

        :param web_element: a bs4 Tag instance
        :return:
        """
        linktag_num = 0
        for child in web_element.children:
            if isinstance(child, Tag):
                self.count_link_tags(child)
        if is_ignorable(web_element, self.ignorable_tags):
            linktag_num = web_element[KG_TAG_NUM]
            self.update_link_chars(web_element)
        else:
            for child in web_element.children:
                if isinstance(child, Tag):
                    linktag_num += child[KG_LINKTAG_NUM]
                    if is_ignorable(child, self.ignorable_tags):
                        linktag_num += 1
                    else:
                        child_linktag_num = child[KG_LINKTAG_NUM]
                        child_tag_num = child[KG_TAG_NUM]
                        child_char_num = child[KG_CHAR_NUM]
                        child_linkchar_num = child[KG_LINKCHAR_NUM]
                        if child_linktag_num == child_tag_num and child_char_num == child_linkchar_num and 0 != child_linktag_num:
                            linktag_num += 1
        web_element[KG_LINKTAG_NUM] = linktag_num


class Extractor(AbstractExtractor):
    """
    The base implementation of the original composite text density extraction
    algorithm
    """

    def count_chars(self, web_element: Tag):
        """
        Modifies the parameter page element by setting an attribute on
        each element denoting the total number of characters in that
        element's text
        :param web_element: a bs4 Tag instance
        :return: void
        """
        if isinstance(web_element, Tag):
            element_str = ' '.join(web_element.stripped_strings)
            num_chars = len(element_str)
            web_element[KG_CHAR_NUM] = num_chars
            for child in web_element.children:
                self.count_chars(child)

    def update_link_chars(self, web_element: Tag):
        """
        The default implementation, presumably meant to sum all link
        characters in the children of the element provided. This method
        is ported verbatim from the original code, where it doesn't seem to do
        anything and just sets the attribute to the same value as the character
        number. Probably why there's a variant method also.

        There's also a note in the original code to ensure that this method is called
        after update_link_chars, for obvious reasons.

        :param web_element: the page element provided
        :return:
        """
        for child in web_element.children:
            if isinstance(child, Tag):
                child[KG_LINKCHAR_NUM] = child[KG_CHAR_NUM]
                self.update_link_chars(child)

    def compute_text_density(self, web_element: Tag, ratio: float):
        """
        Computes the text density of the element provided, and recursively computes it for
        the element's children. This number is essentially a ratio of non-link characters
        to link characters.
        :param web_element:
        :param ratio:
        :return:
        """
        char_num = web_element[KG_CHAR_NUM]
        tag_num = web_element[KG_TAG_NUM]
        linkchar_num = web_element[KG_LINKCHAR_NUM]
        linktag_num = web_element[KG_LINKTAG_NUM]
        if char_num == 0:
            density = 0.
        else:
            un_linkchar_num = char_num - linkchar_num
            if tag_num == 0:
                tag_num = 1
            if linkchar_num == 0:
                linkchar_num = 1
            if linktag_num == 0:
                linktag_num = 1
            if un_linkchar_num == 0:
                un_linkchar_num = 1

            # this formula is copied directly from the src obviously
            density = (char_num / tag_num) * ln(
                (char_num * tag_num) / (linkchar_num * linktag_num)) / ln(
                ln(char_num * linkchar_num / un_linkchar_num + ratio * char_num + math.e))

        web_element[KG_TEXT_DENSITY] = max(density, 0)
        for child in web_element.children:
            if isinstance(child, Tag):
                self.compute_text_density(child, ratio)

    def compute_density_sum(self, web_element: Tag, ratio: float):
        """
        Recursively omputes the sum of text density across the node provided and all subnodes
        :param web_element:
        :param ratio:
        :return:
        """
        density_sum = 0.
        char_num_sum = 0
        content = ' '.join(web_element.stripped_strings)
        from_ = 0

        if isinstance(web_element, Tag):
            for child in web_element.children:
                if isinstance(child, Tag):
                    self.compute_density_sum(child, ratio)
            for child in web_element.children:
                if isinstance(child, Tag):
                    density_sum += child[KG_TEXT_DENSITY]
                    char_num_sum += child[KG_CHAR_NUM]
                    child_content = ' '.join(child.stripped_strings)
                    try:
                        index = content.index(child_content)
                    except:
                        index = -1
                    if index > -1:
                        length = index - from_
                        if length > 0:
                            density_sum += length * ln(1. * length) / ln(ln(ratio * length + math.e))
                            from_ = index + len(child_content)
            length = len(content) - from_
            if length > 0 and ratio * length > (1 / math.e):
                density_sum += length * ln(1. * length) / ln(ln(ratio * length + math.e))

            web_element[KG_DENSITY_SUM] = density_sum


class VariantExtractor(AbstractExtractor):
    """
    A variant of the text density extractor, included in the original source
    with methods described with a "variant" suffix
    """

    def count_chars(self, web_element: Tag):
        """
        Initializes the KG_CHAR_NUM attribute by actually counting
        child characters not included in the current DOM element.
        :param web_element:
        :return:
        """
        char_num = 0
        plain_text_length = len(' '.join(web_element.stripped_strings))
        if not is_ignorable(web_element, self.ignorable_tags) and isinstance(web_element, Tag):
            for child in web_element.children:
                if isinstance(child, Tag):
                    self.count_chars(child)
            for child in web_element.children:
                if isinstance(child, Tag):
                    char_num += child[KG_CHAR_NUM]
                    child_plain_text_length = len(' '.join(child.stripped_strings))
                    plain_text_length -= child_plain_text_length
            char_num = char_num + plain_text_length
        web_element[KG_CHAR_NUM] = char_num

    def update_link_chars(self, web_element: Tag):
        """
        Initializes the KG_CHAR_NUM attribute for all children of the
        element provided to 0, not sure what the point is
        :param web_element:
        :return:
        """
        if isinstance(web_element, Tag):
            for child in web_element.children:
                if isinstance(child, Tag):
                    child[KG_CHAR_NUM] = 0
                    self.update_link_chars(child)

    def compute_text_density(self, web_element: Tag, ratio=0.0):
        """
        Computes text density as a simple ratio of link to non-link characters
        :param web_element:
        :return:
        """
        char_num = web_element[KG_CHAR_NUM]
        tag_num = web_element[KG_TAG_NUM]
        text_density = 0.
        if char_num != 0:
            if tag_num == 0:
                tag_num = 1
            text_density = 1. * char_num / tag_num
        web_element[KG_TEXT_DENSITY] = text_density
        if isinstance(web_element, Tag):
            for child in web_element.children:
                if isinstance(child, Tag):
                    self.compute_text_density(child)

    def compute_density_sum(self, web_element: Tag, ratio=0.0):
        """
        A simpler way of computing the density sum that doesn't do the normalization
        steps that the default method uses
        :param web_element:
        :return:
        """
        density_sum = 0.
        char_num_sum = 0.
        if isinstance(web_element, Tag):
            for child in web_element.children:
                self.compute_density_sum(child)
            for child in web_element.children:
                if isinstance(child, Tag):
                    density_sum += child[KG_TEXT_DENSITY]
                    char_num_sum += child[KG_CHAR_NUM]
            char_num = web_element[KG_CHAR_NUM]
            if char_num > char_num_sum:
                char_num -= char_num_sum
                density_sum += char_num
            else:
                density_sum = web_element[KG_TEXT_DENSITY]
                web_element[KG_DENSITY_SUM] = density_sum

html_tag_regex = re.compile(r'(<HTML>|<html>)(.*)(</HTML>|</html>)')

class EDGARExtractor(Extractor):

    def __init__(self):
        self.removables = JS_TAGS
        self.ignorable_tags = LINK_TAGS.union(JS_TAGS)

    def create_doc(self, html: str) -> BeautifulSoup:
        start = html.index('<html>')
        end = html.index('</html>') + len('</html')
        s = html[start:end + 1]
        return BeautifulSoup(s, 'html.parser').body

    def extract_content(self, html: str) -> str:
        bs = self.create_doc(html)
        self.preprocess_dom(bs)
        self.count_chars(bs)
        self.count_tags(bs)
        self.count_link_chars(bs)
        self.count_link_tags(bs)
        char_num = bs[KG_CHAR_NUM]
        linkchar_num = bs[KG_LINKCHAR_NUM]
        ratio = linkchar_num / char_num
        self.compute_text_density(bs, ratio)
        self.compute_density_sum(bs, ratio)

        # kill everything with no density
        kws = {KG_DENSITY_SUM: 0}
        zero_elements = bs.find_all(**kws)
        [z.extract() for z in zero_elements]
        output_dirty = bs.get_text()
        # remove excess whitespace and duplicate newline characters
        output_dirty = whitespace_regex.sub(' ', output_dirty)
        output = '\n'.join(list(filter(lambda s: len(s.strip()) > 0, output_dirty.splitlines())))
        return output


if __name__ == '__main__':
    sample = open('/Users/blevine/composite-text-density/SEC-AAPL-10K.txt', 'rb').read().decode('utf-8', errors='ignore')
    ext = EDGARExtractor()
    extr = ext.extract_content(sample)
    # write to file
    SEC_APPL = open('SEC-AAPL-10K-clean.txt', 'wb')
    SEC_APPL.write(extr.encode('utf8', errors='ignore'))
    print('Wrote %d characters to file' % (len(extr)))