# Content extraction via text density

This is a small, single-file library for the purpose of cleaning open web data (scraped HTML) to the point where 
it can be used for machine learning and natural language processing
tasks. It does so by essentially comparing the ratio of hyperlink text to non-hyperlink text for each DOM node (the "text density"), then 
extracting a cohesive tree based on that metric. It is based on a paper from the Beijing Institute of Technology, which is linked below. 

This is largely a direct port of the authors' original C++/Qt code, and language- and library-specific optimizations have been foregone 
to ensure fidelity to the original algorithm. The only significant deviations from the original code are that this implementation also excludes `style` and `script` nodes from the final output,
 regardless of their density scores, methods are encapsulated in objects where applicable, and the algorithm returns a cleaned version of the text instead of a DOM tree--but 
 this can be changed by removing a few lines in the `extract_content()` method.


Original paper: http://ofey.me/papers/cetd-sigir11.pdf

Original code: https://github.com/FeiSun/ContentExtraction

### To Install (Python 3.4+):
`python setup.py install`

That should work, otherwise all this project requires is `beautifulsoup4` from PyPI:

`pip install beautifulsoup4`

This code was written with Python 3.6.3. It will not work with Python versions prior to 3.4. 

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
