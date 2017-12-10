from abc import ABC, abstractmethod
from math import log, exp

from bs4 import BeautifulSoup, Tag, NavigableString, PageElement

# these constants are defined as NavigableStrings to
# coincide with the original implementation's use of QString.
# There isn't really a point to using this instead of raw values
# other than ensuring this code corresponds directly to the original

KG_CHAR_NUM = NavigableString('char-number'),
KG_TAG_NUM = NavigableString('tag-number'),
KG_LINKCHAR_NUM = NavigableString('linkchar-number'),
KG_LINKTAG_NUM = NavigableString('linktag-number'),
KG_TEXT_DENSITY = NavigableString('text-density'),
KG_DENSITY_SUM = NavigableString('density-sum'),
KG_MAX_DENSITY_SUM = NavigableString('max-density-sum'),
KG_MARK = NavigableString('mark'),
KG_GEOMETRY = NavigableString('geometry')


def search_tag(web_element, attribute, value: float):
    pass


def get_file_list(path):
    pass


def is_link_tag(tag: Tag):
    return repr(tag.name).lower() in {'a', 'button', 'select'}


class AbstractExtractor(ABC):
    """
    An abstract superclass encapsulating most of the functionality of
    the composite text density extraction algorithm, leaving a few methods
    open to variable implementations
    """

    def extract_content(self, html: str) -> str:
        bs = BeautifulSoup(html, 'html.parser').body

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

    def find_max_density_sum(self, web_element: Tag) -> float:
        pass

    def get_threshold(self, web_element: Tag, max_density_sum: float) -> float:
        pass

    def set_mark(self, web_element: Tag, max_density_sum: float):
        pass

    def mark_content(self, web_element: Tag, threshold: float):
        pass

    def count_tags(self, web_element: Tag):
        """
        Counts the number of tags in the descendants of the element provided
        :param web_element:
        :return: void
        """
        tag_num = 0
        if web_element.next_element is not None:
            for child in web_element.descendants:
                if isinstance(child, Tag):
                    self.count_tags(child)
            for child in web_element.descendants:
                if isinstance(child, Tag):
                    tag_num += child[KG_TAG_NUM]
        web_element[KG_TAG_NUM] = NavigableString(tag_num)

    def count_link_chars(self, web_element: Tag):
        """
        Recursively counts all link characters in the descendants of the tag provided
        :param web_element:
        :return:
        """
        linkchar_num = 0
        for child in web_element.descendants:
            if isinstance(child, Tag):
                self.count_link_chars(child)
        if is_link_tag(web_element):
            linkchar_num = int(web_element[KG_CHAR_NUM])
            self.update_link_chars(web_element)
        else:
            for child in web_element.descendants:
                if isinstance(child, Tag):
                    linkchar_num += int(child[KG_LINKCHAR_NUM])
        web_element[KG_LINKCHAR_NUM] = NavigableString(linkchar_num)

    def update_link_tags(self, web_element: Tag):
        """
        Recursively updates this tag and all its descendants with the number of
        link tags in the tree they're currently in.
        :param web_element:
        :return:
        """
        for child in web_element.descendants:
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
        for child in web_element.descendants:
            if isinstance(child, Tag):
                self.count_link_tags(child)
        if is_link_tag(web_element):
            linktag_num = int(web_element[KG_TAG_NUM])
            self.update_link_chars(linktag_num)
        else:
            for child in web_element.descendants:
                if isinstance(child, Tag):
                    linktag_num += int(child[KG_LINKTAG_NUM])
                    if is_link_tag(child):
                        linktag_num += 1
                    else:
                        child_linktag_num = int(child[KG_LINKTAG_NUM])
                        child_tag_num = int(child[KG_TAG_NUM])
                        child_char_num = int(child[KG_CHAR_NUM])
                        child_linkchar_num = int(child[KG_LINKCHAR_NUM])
                        if child_linktag_num == child_tag_num and child_char_num == child_linkchar_num and 0 != child_linktag_num:
                            linktag_num += 1
        web_element[KG_LINKTAG_NUM] = NavigableString(linktag_num)


class Extractor(AbstractExtractor):
    """
    The base implementation of the original composite text density extraction
    algorithm
    """

    def count_chars(self, web_element: PageElement):
        """
        Modifies the parameter page element by setting an attribute on
        each element denoting the total number of characters in that
        element's text
        :param web_element: a bs4 Tag instance
        :return: void
        """
        num_chars = len(repr(web_element.string).strip())
        web_element[KG_CHAR_NUM] = num_chars
        if isinstance(web_element, Tag):
            for child in web_element.descendants:
                self.count_chars(child)

    def update_link_chars(self, web_element: Tag):
        """
        The default implementation, presumably meant to sum all link
        characters in the descendants of the element provided. This method
        is ported verbatim from the original code, where it doesn't seem to do
        anything and just sets the attribute to the same value as the character
        number. Probably why there's a variant method also.

        There's also a note in the original code to ensure that this method is called
        after update_link_chars, for obvious reasons.

        :param web_element: the page element provided
        :return:
        """
        for child in web_element.descendants:
            if isinstance(child, Tag):
                child[KG_LINKCHAR_NUM] = child[KG_CHAR_NUM]
                self.update_link_chars(child)

    def compute_text_density(self, web_element: Tag, ratio: float):
        char_num = web_element[KG_CHAR_NUM]
        tag_num = web_element[KG_TAG_NUM]
        linkchar_num = web_element[KG_LINKCHAR_NUM]
        linktag_num = web_element[KG_LINKTAG_NUM]
        density = 0.
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
            density = (1.0 * char_num / tag_num) * log(
                (1.0 * char_num * tag_num) / (1.0 * linkchar_num * linktag_num)) / log(
                log(1.0 * char_num * linkchar_num / un_linkchar_num + ratio * char_num + exp(1.0)))

            web_element[KG_TEXT_DENSITY] = NavigableString(density)
            for child in web_element.descendants:
                if isinstance(child, Tag):
                    self.compute_text_density(child, ratio)

    def compute_density_sum(self, web_element: PageElement, ratio: float):
        density_sum = 0.
        char_num_sum = 0
        content = web_element.string
        from_ = 0
        index = 0
        length = 0

        # if web_element.n


class VariantExtractor(AbstractExtractor):
    """
    A variant of the text density extractor, included in the original source
    with methods described with a "variant" suffix
    """

    def count_chars(self, web_element: Tag):
        pass

    def update_link_chars(self, web_element: Tag):
        pass

    def compute_text_density(self, web_element: Tag):
        pass

    def compute_density_sum(self, web_element: Tag):
        pass
