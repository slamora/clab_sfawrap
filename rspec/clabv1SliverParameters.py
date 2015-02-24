'''
Created on Jun 4, 2014

@author: gerard
'''
from sfa.rspecs.elements.element import Element

class Clabv1SliverParameters(Element):
    fields = [
        'template',
        'sliver_interfaces',
    ]


class Clabv1Template(Element):
    fields = [
        'name',
        'id',
    ]


class Clabv1NetworkInterface(Element):
    fields = [
        'name',
        'type',
        'nr',
    ]
