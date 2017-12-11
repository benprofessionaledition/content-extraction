# Content extraction via text density
Anyone who has ever played with actual web data and not just Twitter datasets knows that web data is complete garbage. This is
a pure Python implementation of content extraction via composite text density. The overall 
idea of the algorithm is to detect which parts of a web page are relevant by comparing the "text 
density," which is a metric derived from the ratio of hyperlink to non-hyperlink characters, of 
all DOM nodes in the tree. Those DOM nodes determined to be relevant then have their text portions
included in the final output. There's some additional logic in there to ensure that a comprehensive 
tree is pulled out and not just the single highest text density node. Additional logic can be implemented 
to exclude nodes in that tree like image captions that aren't relevant. 

The original code is a little painful, as it's written in C++ and requires Qt, 
but other than a few bits, that code has largely been copied verbatim (while watching three and a half straight seasons of Archer) 
to ensure fidelity to the original algorithm. In a future release I may leverage aspects of 
the bs4 library and the Python language to make this code cleaner and more performant. 
The only significant deviation from the original code is that this implementation also excludes `style` and `script` nodes from the final output,
 regardless of their density scores. The original paper was published in 2011, 
so I'll give them a break for that. 

The intended use case of this algorithm is to clean open web data to the point where 
it can be used for machine learning and natural language processing 
tasks. Some garbage will always be present, but TF-IDF/BM25F usually takes 
care of all that. 

Original paper: http://ofey.me/papers/cetd-sigir11.pdf

Original code: https://github.com/FeiSun/ContentExtraction

### To Install (Requires Python 3):
`python setup.py install`

That should work, otherwise all this project requires is `beautifulsoup4` from PyPI:

`pip install beautifulsoup4`
### To use:
```angular2html
from cetd.extractor import Extractor

ext = Extractor()
sample = open('my_html_sample.html', 'rb').read().decode('utf-8', errors='ignore')
extracted = ext.extract_content(sample)
print(extracted)
```
Also included is a `VariantExtractor` class that uses so-called "variant" methods from the original C++ code. The major difference is just that 
it computes the text density as a simple ratio of ignorable to non-ignorable characters, whereas the basic `Extractor` has a bunch of extra 
logic to normalize the ratio. 


#### Future improvements:
- bs4 "descendants" eliminate the need for recursion
- python list comprehensions are substantially more performant than for loops
- destructively modifying DOM nodes is an antipattern 
- reduce the number of passes over the DOM
- figure out how to eliminate the need to constantly check if a pageelement is a tag or navigablestring
- algorithmic improvements: implement better smoothing and add weight to characters in important tags (`article`, `main`, etc)
- make it generalizable so more than link chars can be used to determine relevance 
