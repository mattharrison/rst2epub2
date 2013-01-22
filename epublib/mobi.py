import logging
import math

from genshi.template import MarkupTemplate, NewTextTemplate
from genshi.template import TemplateLoader
from genshi.core import Markup
from epublib import epub

logging.basicConfig(level=logging.DEBUG)
# see http://blog.epubandebookhelp.com/2012/05/16/kf8-panel-magnification/
# and amazon sample book
# http://mathorsinfotech.blogspot.com/2012/06/kf8-fixed-layout-image-zoom-tutorial.html
class MobiComicBook(epub.EpubBook):
    def __init__(self, width=600,
                 height=1024,
                 book_type='comic',
                 region_magnification='true',
                 orientation_lock='none',
                 add_jquery=False):
        epub.EpubBook.__init__(self)
        self.comic_meta = []
        self.add_comic_meta('fixed-layout', 'true')
        self.add_comic_meta('orientation-lock', 'portrait' )#orientation_lock)
        self.add_comic_meta('RegionMagnification', 'true')
        self.width = width
        self.height = height
        resolution = '{0}x{1}'.format(width, height)
        self.add_comic_meta('original-resolution', resolution)
        # if book type not specified images limited to 256K
        self.add_comic_meta('book-type', book_type)

        self.add_comic_meta('zero-gutter', 'true')
        self.add_comic_meta('zero-margin', 'true')


        self.pages = []
        self.page = None
        self.ordinal = 1
        self.target_id = 1

        self.add_jquery = add_jquery

    def get_target_id(self):
        tid =  'zoom{0}'.format(self.target_id)
        self.target_id += 1
        return tid

    def get_ordinal(self):
        # appears to be global for book
        self.ordinal += 1
        return self.ordinal - 1

    def get_meta_tags(self):
        tags = epub.EpubBook.get_meta_tags(self)
        value = end = ''
        for name, content in self.comic_meta:
            tags.append(('<meta name="{0}" content="{1}"/>'.format(name, content), value, end))
        return tags


    def add_comic_meta(self, name, content):
        self.comic_meta.append((name, content))

    def add_page(self):
        page = Page(self)
        self.pages.append(page)
        return page



class Mag(object):
    def __init__(self, txt, target_id_parent, target_id,
                 left, top, width, height,
                 lb_left, lb_top, lb_width, lb_height,
                 zoomed_img_left, zoomed_img_top,
                 img_src, ordinal=None, zoom_factor=1.5,
                 pre_data=None, post_data=None):
        self.txt = txt
        self.target_id_parent = target_id_parent
        self.target_id = target_id

        # coordinates for click target
        self.top = top
        self.left = left
        self.height = height
        self.width = width

        # lb_ refers to lightbox image
        self.lb_top = lb_top
        self.lb_left = lb_left
        self.lb_width = lb_width
        self.lb_height = lb_height

        # zoomed_img_ referes to position on zoomed image relative to lightbox
        self.zoomed_img_top = zoomed_img_top
        self.zoomed_img_left = zoomed_img_left

        self.ordinal = ordinal
        self.zoom_factor = zoom_factor
        self.img_src = img_src
        #text/etc to display
        if post_data:
            self.post_data = Markup(post_data)
        else:
            self.post_data = ''
        if pre_data:
            self.pre_data = Markup(pre_data)
        else:
            self.pre_data = ''

    @property
    def target_id_mag(self):
        return self.target_id + "-magTarget"


    def json_junk(self):
        # kf8 really cares about double quotes on the inside...
        # only took 33 attempts to figure this out
        result = '{{"targetId":"{0}", "ordinal":{1} }}'.format(self.target_id_parent, self.ordinal)
        return result

LEFT=1
RIGHT=2
DOWN=3
UP=4

class Page(object):
    PARENT_SUFFIX = '-magTargetParent'
    def __init__(self, book, height=1024, width=600):
        self.img = None
        self.book = book
        self.mags = []
        self.title = None
        self.style = None
        self.height = height
        self.width = width


    def __iter__(self):
        for mag in self.mags:
            yield mag

    def add_bg_image(self, src_path, dest_path, id=None):
        self.img = self.book.add_image(src_path, dest_path, id)

    def auto_target(self,
                    whole_target_left, whole_target_top, whole_target_width, whole_target_height,
                    zoom_factor=2, overlap_percent=10, direction=LEFT,
                    post_data=None,
                    txt=None):
        start_left = whole_target_left
        # target is all in percent
        print "ZF", zoom_factor
        if direction == LEFT:
            chunks = whole_target_width*zoom_factor/100.
            chunk_int = int(math.ceil(chunks))
            target_left = whole_target_left
            zoom_left = whole_target_left
            print "CHUNKS", chunks, "WHOLE WIDTH", whole_target_width
            for i in range(chunk_int):
                if chunks > 1:
                    target_width = whole_target_width/float(chunks)
                else:
                    target_width = whole_target_width
                right_side = target_left + target_width
                if right_side > 100: #whole_target_width:
                    #target_width = right_side - target_left
                    target_left = 100 - target_width
                    zoom_left = 100 - target_width
                elif right_side > start_left + whole_target_width:
                    print "OFF RIGHT",
                    target_left = whole_target_left + whole_target_width - target_width
                    zoom_left = whole_target_left + whole_target_width - target_width
                    #target_width = whole_target_width # - target_left
                print "LEFT", target_left
                print "RIGHT SIDE", right_side, "TW", target_width

                print "H", self.book.height, "MINUS", - whole_target_height*zoom_factor/2.
                lb_width = 100
                lb_left = 0
                if whole_target_width * zoom_factor < 100:
                    print "SMALLER", whole_target_width * zoom_factor
                    lb_width = whole_target_width * zoom_factor
                    lb_left = 50 - lb_width/2
                self.add_zoom_image(zoom_factor,
                    target_left, whole_target_top, target_width, whole_target_height,
                    lb_left, 50. - whole_target_height*zoom_factor/2., lb_width, whole_target_height*zoom_factor,
                    -zoom_left, 0 - 100*(whole_target_top/float(whole_target_height)/zoom_factor),
                    txt=txt,post_data=post_data)
                #zoom_left, -whole_target_top*zoom_factor)

                zoom_left += target_width
                target_left += whole_target_width/float(chunks)
                #target_left += (whole_target_width - target_width)/float(chunks)

    def add_zoom_image(self, zoom_factor,
                       target_left, target_top, target_width, target_height,
                       lb_left, lb_top, lb_width, lb_height,
                       zoom_left, zoom_top,
                       src_path=None, dest_path=None, txt=None,
                       pre_data=None, post_data=None):
        # post data is borked
        logging.debug("ZOOM IMAGE: tl:{0} tt:{1}: tw:{2} th:{3}\n lb_l:{4} lb_t:{5} lb_w:{6}, lb_h:{7}\n  zl:{8} zt:{9}".format(
            target_left, target_top, target_width, target_height,
              lb_left, lb_top, lb_width, lb_height,
              zoom_left, zoom_top
            ))
        print "BAR"
        if src_path and dest_path:
            img = self.book.add_image(src_path, dest_path, None)
        else:
            img = self.img
        tid = self.book.get_target_id()
        ordinal = self.book.get_ordinal()
        mag = Mag(txt, tid+self.PARENT_SUFFIX, tid,
            int(target_left), int(target_top), int(target_width), int(target_height),
            int(lb_left), int(lb_top), int(lb_width), int(lb_height),
            int(zoom_left), int(zoom_top),
            img.dest_path, ordinal,
            pre_data=pre_data, post_data=post_data,
            zoom_factor=zoom_factor)
        self.mags.append(mag)

    def to_html(self):
        #temp = NewTextTemplate(PAGE_TEMPLATE)
        temp = self.book.loader.load('mobicomic2.html')
        stream = temp.generate(page=self, body='', img_src=self.img.dest_path,
                               add_jquery=self.book.add_jquery)
        html = stream.render('html', doctype= 'html-transitional')
        return html

    def add_html(self, dest_path):
        return self.book.add_html('', dest_path, self.to_html())


TEST_HTML = """
        <!DOCTYPE html SYSTEM "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">

<head>
	<title>KF8 SAMPLE TEMPLATE</title>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
  <style>
  /*
Copyright (c) 2010, Yahoo! Inc. All rights reserved.
Code licensed under the BSD License:
http://developer.yahoo.com/yui/license.html
version: 3.3.0
build: 3167
*/
html{color:#000;background:#FFF;}body,div,dl,dt,dd,ul,ol,li,h1,h2,h3,h4,h5,h6,pre,code,form,fieldset,legend,input,textarea,p,blockquote,th,td{margin:0;padding:0;}table{border-collapse:collapse;border-spacing:0;}fieldset,img{border:0;}address,caption,cite,code,dfn,em,strong,th,var{font-style:normal;font-weight:normal;}li{list-style:none;}caption,th{text-align:left;}h1,h2,h3,h4,h5,h6{font-size:100%;font-weight:normal;}q:before,q:after{content:'';}abbr,acronym{border:0;font-variant:normal;}sup{vertical-align:text-top;}sub{vertical-align:text-bottom;}input,textarea,select{font-family:inherit;font-size:inherit;font-weight:inherit;}input,textarea,select{*font-size:100%;}legend{color:#000;}

@font-face {
	font-family: "Booter 5-0";
	font-style: normal;
	font-weight: normal;
	src: url(../fonts/Booter_5-0.ttf);
}

body {
	font-family: "Booter 5-0";
	font-size: 210%;
}

div.fs {
  height: 1024px;
  width: 600px;
  position: relative;
}

div.fs div {
  position: absolute;
}

div.fs a {
  display: block;
  width : 100%;
  height: 100%;
}

.image {
  position: absolute;
  height: 1024px;
  width: 600px;
}


div.note {
	top: 10%;
	left: 0%;
	width: 100%;
}

div.center {
	position: absolute;
	top: 42%;
	left: 29%;
	width: 40%;
  border: 4px solid #000000;
}

h1 {	font-family: "Booter 5-0";
	font-size: 45px;
	position: relative;
	text-align: center;
	text-shadow: 1px 1px 3px #1a1a1a;
	top: 0px;
}
h2 {	font-family: "Booter 5-0";
	font-size: 32px;
	position: relative;
	text-align: center;
	font-style: italic;
	text-shadow: 1px 1px 3px #1a1a1a;
	top: 30px;
}

p {
	font-family: "Booter 5-0";
	font-style: italic;
	position: relative;
	text-align: center;
	text-shadow: 1px 1px 3px #1a1a1a;
}

p.textzoom {
	font-size: 150%;
	margin: 20%;
	top: 18%;
	z-index: 1;
}

div.target-mag {
  position: absolute;
  display: block;
  overflow: hidden;
  /* UI Styling */
  border: 5px solid  #000000;
}

/* Actual image resolution */
div.target-mag img {
  position: absolute;

  height: 3000px;
  /*height: 1536px;
    width: 900px;*/
  width: 1800px;
}
div.target-mag-parent {
	width:100%;
	height:100%;
	display:none;
}
div.target-mag-lb {
	height: 100%;
	width: 100%;
	background: #333333;
	opacity:.75;
}

/* Use the following to define the zoom levels */
/* zoom100 equals the default display size */

div.target-mag img.zoom100 {
  position: absolute;
  height: 1024px;
  width: 600px;
}

/* Enter the actual height and width of the image here: this is the zoom factor, regardless of what number you enter in the tag at zoom### - that number only need be larger than 100, but otherwise has no effect on the amount of magnification */

div.target-mag img.zoom150 {
  position: absolute;
  height: 1536px;
  width: 900px;
}

/* Tap Target Zone Size & Position */
#zoom1 {
	top: 30%;
	left: 15%;
	height: 45%;
	width: 70%;
}
/* Magnified Region Size & Position */
#zoom1-magTarget {
	top: 21%;
	left: 0%;
	height: 62%;
	width: 100%;
}
/* Image Offset */
#zoom1-magTarget img {
	top: -77%;
	left: -25%;
}


/* Magnified text box formatting */

/* Default content */

p.text {
	font-size: 100%;
	border: 4px solid #000000;
	padding: 10px;
}

.app-amzn-magnify {
 background-color: green;
border: 5px solid  #000000;
opacity: .5;
}


</style>
</head>

<body>

<!-- This is an example of how to use region zoom to magnify an image -->
	<div class="fs">
		<div>
			<img src="img3.jpeg" alt="The Serpent Ring" class="image"/>
		</div>

		<div class="note">
			<h1>Example of Panel View<br/>
			with Lightbox effect</h1>
			<h2>showing how to use live text<br/>
			within a magnified image</h2>
		</div>


     <div id="zoom1">
<!--			<a class="app-amzn-magnify" data-app-amzn-magnify="{'targetId':'zoom1-magTargetParent', 'ordinal':4}" works='False'> -->
			<a class="app-amzn-magnify" data-app-amzn-magnify='{"targetId":"zoom1-magTargetParent", "ordinal":4}' works='True'>
              <div><p class="center">BEFORE</p></div>
            </a>
      </div>

      <div id="zoom1-magTargetParent" class="target-mag-parent">
        <div class="target-mag-lb"></div>
        <div id="zoom1-magTarget" class="target-mag">
          <h2>AFTER</h2>
          <img src="img1.jpeg" alt="">
        </div>
      </div>


	</div>

</body>
</html>

        """

def test():
    book = MobiComicBook(add_jquery=True)
    title = 'Test Comic35'
    book.set_title(title)
    cov_image = 'data/little-nemo-19051015-l.jpeg'
    book.add_cover(cov_image, title=title)
    page = book.add_page()
    page.add_bg_image('data/little-nemo-19051015-l.jpeg', 'img1.jpeg')
    #page.add_mag('foo_id_parent', 'foo_id', 20, 20, 30, 60, 30, 30)
    page.auto_target(50, 1*100./6, 50, 100./6, #target_left, target_top, target_width, target_height,
                    zoom_factor=3, post_data='<p class="textzoom">TEST DATA</p>')
    # page.auto_target(0, 0, 100, 100./6, #target_left, target_top, target_width, target_height,
    #                 zoom_factor=2)
    # for row in range(1,5):
    #     page.auto_target(0, row*100./6, 50, 100./6, #target_left, target_top, target_width, target_height,
    #                 zoom_factor=2)
    #     page.auto_target(50, row*100./6, 50, 100./6, #target_left, target_top, target_width, target_height,
    #                 zoom_factor=2)
    for col in range(4):
        page.auto_target(col*25, 500./6, 25, 100./6, #target_left, target_top, target_width, target_height,
                    zoom_factor=2)

        #page.add_zoom_image(1.5,50,0,100./6,50,50,0,100,20,0,50,pre_data='<div><p class="center">BEFORE</p></div>')
    h1 = page.add_html('1.html')
    book.add_spine_item(h1)

    # page = book.add_page()
    # page.add_bg_image('data/little-nemo-19051022-l.jpeg', 'img2.jpeg')
    # page.add_zoom_image(1.5, 0,0,50,50,0,0,pre_data='<p>BEFORE</p>',
    #                     post_data='<h2>AFTER</h2>')
    # h2 = page.add_html('2.html')
    # book.add_spine_item(h2)

    page.add_bg_image('data/little-nemo-19051105-l.jpeg', 'img3.jpeg')
    h3 = book.add_html('', '3.html', TEST_HTML)
    book.add_spine_item(h3)
    directory = '/tmp/mobitest'
    book.create_book(directory)
    book.create_archive(directory, directory + '.epub')


if __name__ == '__main__':
    test()
