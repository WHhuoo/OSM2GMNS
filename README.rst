OSM2GMNS
========

OSM2GMNS is an open-source python package which can help users easily convert networks 
from `OpenStreetMap <https://www.openstreetmap.org/>`_ to .csv files with 
standard `GMNS <https://github.com/zephyr-data-specs/GMNS>`_ format for visualization, 
traffic simulation and planning purpose.

Install
-------

Install OSM2GMNS via pip::

    $ pip install osm2gmns

Simple example
--------------

Get network from map.osm file and consolidate complex intersections

.. code:: python

    >>> import networkx as nx
    >>> net = og.getNetFromOSMFile('map.osm')
    >>> og.outputNetToCSV(net)
    # check and modify (if necessary) network files before complex intersection consolidation
    >>> net = og.getNetFromCSV()
    >>> og.consolidateComplexIntersections(net)
    >>> og.outputNetToCSV(net, output_folder='consolidated')

Visualization
-------------

You can visualize generated networks using `NeXTA <https://github.com/xzhou99/NeXTA-GMNS>`_ 
or `QGis <https://qgis.org/>`_.

.. image:: https://github.com/jiawei92/OSM2GMNS/blob/master/test/asu.PNG

Download the map
-------------
Open`OpenStreetMap <https://www.openstreetmap.org/>`_  
Click the Export/ Export button at the top of the page.  
Click on the "Manually select a company area", and then you can choose in the map on the right side area.  
Click the blue "Export" button in the left operation area of the page to save the *.osM file in the target area.
