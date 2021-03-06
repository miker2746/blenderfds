"""BlenderFDS, types"""

import bpy, time, sys
from bpy.props import *
from bpy.types import Scene, Object, Material

from . import config, geometry, fds
from .exceptions import BFException
from .utils import is_iterable, ClsList

DEBUG = False


#++ Decorators

def subscribe(cls):
    """Subscribe class to related collections."""
    # Transform self.bf_props from List to ClsList
    cls.bf_props = ClsList(cls.bf_props)
    # Subscribe to class collection 'self.all'
    cls.all.append(cls)
    # Subscribe to other useful dicts, but init specific dict for each new class
    # Build my cls.all_bf_props
    cls.all_bf_props = ClsList()
    if cls.bf_prop_export:
        cls.all_bf_props.append(cls.bf_prop_export)
    for bf_prop in cls.bf_props:
        cls.all_bf_props.append(bf_prop)
        cls.all_bf_props.extend(bf_prop.all_bf_props)
    # Return
    return cls


#++ BF specific types

# BFProp and BFNamelist are used for short lived instances.
# When calling a Blender Element bf_namelist or bf_namelists method,
# the BFNamelist and all related BFProps are instantiated, then quickily forgotten
# This mechanism is used to draw panels and to export to FDS.

#@subscribe This will be used to subscribe the class to the collections
class _BFCommon():
    """Common part of BFProp and BFNamelist"""

    all = ClsList()           # Collection of all classes of my type
                              # Generated by @subscribe decorator, inited on class type
    all_bf_props = ClsList()  # Collection of all my managed bf_props, included descendants
                              # Generated by @subscribe decorator, inited on each class

    label = "No Label"        # Object label
    description = ""          # Object description
    enum_id = 0               # Unique integer id for EnumProperty
    fds_label = None          # FDS label, eg. "OBST", "ID", ...
    fds_default = None        # FDS default value, eg. True.
                              # The BFProp is not exported when value is fds_default.
    fds_separator = " "       # FDS separator between parameters
    fds_cr = "\n      "       # FDS carriage return

    bf_prop_export = None     # Class of type BFExportProp, used for setting if exported
    bf_props =  ClsList()     # Collection of related BFProp

    bf_other = {}             # Other optional BlenderFDS parameters,
                              # eg: {'copy_protection': True, 'draw_type': 'WIRE', ...}

    bpy_type = None           # type in bpy.types for Blender property, eg. Object
    bpy_idname = None         # idname of related bpy.types Blender property, eg. "bf_id"
    bpy_prop = None           # prop in bpy.props of Blender property, eg. StringProperty
    bpy_other = {}            # Other optional Blender property parameters,
                              # eg. {"min": 3., ...}
                              # the eventual "default" is the displayed default
                              # and has no effect in exporting to FDS

    def __init__(self, element):
        # The instance contains the reference to the element
        self.element = element
        # Replace linked BFProp classes with their instances
        if self.bf_prop_export:
            self.bf_prop_export = self.bf_prop_export(element)
        if self.bf_props:
            self.bf_props = ClsList((bf_prop(element) for bf_prop in self.bf_props))
        # Init exporting variables
        self.infos = list()

    def __repr__(self):
        return "{__class__.__name__!s}(element={element!r})".format(
            __class__ = self.__class__, **self.__dict__)

    # Generated properties

    @property
    def bf_prop_free(self):
        for bf_prop in self.bf_props:
            if isinstance(bf_prop, BFFreeProp):
                return bf_prop

    # Register/Unregister

    @classmethod
    def register(cls):
        """Register all related Blender properties."""
        DEBUG and print("BFDS: BFProp.register:", cls.__name__)
        if not cls.bpy_type:
            raise Exception("No bpy_type in class '{}'".format(str(cls)))
        # Insert fds_default
        if cls.fds_default is not None:
            # ...in description
            cls.description += " [{}]".format(cls.fds_default)
            # ...in bpy_other if not present
            if "default" not in cls.bpy_other:
                cls.bpy_other["default"] = cls.fds_default
        # Register my own Blender property, if not already present
        if cls.bpy_prop and cls.bpy_idname and not hasattr(cls.bpy_type, cls.bpy_idname):
            if DEBUG:
                print("BFDS:  ", '{}.{} = {}(name="{}")'.format(
                    cls.bpy_type.__name__,
                    cls.bpy_idname,
                    cls.bpy_prop.__name__,
                    cls.label
                ))
            setattr(
                cls.bpy_type,
                cls.bpy_idname,
                cls.bpy_prop(name=cls.label, description=cls.description, **cls.bpy_other)
            )

    @classmethod
    def unregister(cls):
        """Unregister all related Blender properties."""
        DEBUG and print("BFDS: BFProp.unregister:", str(cls)) # TODO unregister

    # UI

    def _draw_messages(self, context, layout) -> "None":
        """Draw messages."""
        # Check self and trap errors
        try:
            self.check(context)
        except BFException as err:
            err.draw(context, layout)
        # Draw infos
        for info in self.infos:
            if is_iterable(info):
                row = layout.split(.7)
                row.label(icon="INFO", text=info[0])
                row.operator(info[1])
            else:
                layout.label(icon="INFO", text=info)

    # Check

    def check(self, context):
        """Check self, append str infos to self.infos, on error raise BFException."""
        pass

    # Export

    def get_value(self) -> "any or None":
        """Get my Blender property value for element."""
        # None is not accepted as attribute name, replaced with str()
        return getattr(self.element, self.bpy_idname or str(), None)

    def set_value(self, context, value) -> "any or None":
        """Set my Blender property to value for element."""
        # Do not raise BFException here. Check is performed by UI, do not add overhead!
        if self.bpy_idname:
            setattr(self.element, self.bpy_idname, value)

    def get_exported(self, context) -> "bool":
        """Return True if self is exported to FDS."""
        if self.fds_default is None:
            if self.bf_prop_export:
                return bool(self.bf_prop_export.get_value())
            else:
                return True
        else:
            if self.bf_prop_export:
                return bool(self.bf_prop_export.get_value()) and self.get_value() != self.fds_default
            else:
                return self.get_value() != self.fds_default

    def set_exported(self, context, value) -> "any or None":  # FIXME used?
        """Set to value if self is exported to FDS."""
        if self.bf_prop_export:
            self.bf_prop_export.set_value(context, value)

    def set_default_value(self, context) -> "any or None":  # FIXME used?
        """Set my Blender property to default value for element."""
        default = self.bpy_other.get("default", None)  # get displayed default
        if default is not None:
            self.set_value(context, default)

    def set_default(self, context) -> "any or None":  # FIXME used?
        """Set me to default for element."""
        self.set_default_value(context)
        for bf_prop in self.all_bf_props:
            bf_prop(self.element).set_default_value(context) # Instantiate!


class BFProp(_BFCommon):
    """BlenderFDS property, interface between a Blender property and an FDS parameter."""

    all = ClsList()  # re-init to obtain specific collection
    all_bf_props = ClsList()

    def __str__(self):
        return "{} > Parameter {}".format(
            str(self.element),
            self.fds_label or self.label or self.__name__,
            )

    # UI

    def _transform_layout(self, context, layout) -> "layout":
        """If self has a bf_prop_export, prepare double-column Blender panel layout."""
        layout = layout.row()
        if self.bf_prop_export:
            # Set two distinct colums: layout_export and layout_ui
            layout_export, layout = layout.column(), layout.column()
            layout_export.prop(self.element, self.bf_prop_export.bpy_idname, text='')
            layout.active = self.bf_prop_export.get_value()
        else:
            layout = layout.column()
        # If not exported, layout is inactive. Protect it from None
        return layout

    def _draw_body(self, context, layout) -> "None":
        """Draw bpy_prop."""
        if not self.bpy_idname:
            return
        row = layout.row()
        row.prop(self.element, self.bpy_idname, text=self.label)

    def draw(self, context, layout) -> "None":
        """Draw my part of Blender panel."""
        layout = self._transform_layout(context, layout)
        self._draw_body(context, layout)
        self._draw_messages(context, layout)

    # Export

    def format(self, context, value):
        """Format to FDS notation."""
        # Expected output:
        #   ID='example' or PI=3.14 or COLOR=3,4,5
        if value is None:
            return None
        # If value is not an iterable, then put it in a tuple
        if not is_iterable(value):
            values = tuple((value,))
        else:
            values = value
        # Check first element of the iterable and choose formatting
        if   isinstance(values[0], bool):
            value = ",".join(value and ".TRUE." or ".FALSE." for value in values)
        elif isinstance(values[0], int):
            value = ",".join(str(value) for value in values)
        elif isinstance(values[0], float):
            value = ",".join("{:.{}f}".format(value, self.bpy_other.get("precision",3)) for value in values)
        elif isinstance(values[0], str) and value: # value is not ""
            value = ",".join("'{}'".format(value) for value in values)
        else:
            return None
        # Return
        if self.fds_label:
            return "=".join((self.fds_label, value))
        return str(value)

    def to_fds(self, context) -> "str or None":
        """Get my exported FDS string, on error raise BFException."""
        if not self.get_exported(context):
            return None
        self.check(context)
        value = self.get_value()
        return self.format(context, value)

    # Import

    def from_fds(self, context, value):
        """Set my value from value in FDS notation, on error raise BFException.
        Value is any type of data compatible with bpy_prop
        Eg: "String", (0.2,3.4,1.2), ...
        """
        DEBUG and print("BFDS: BFProp.from_fds:", str(self), value)
        try:
            self.set_value(context, value)
        except:
            raise BFException(self, "Error importing '{}' value".format(value))
        self.set_exported(context, True)  # Do not export, if errors raised


class BFNamelist(_BFCommon):
    """BlenderFDS namelist, interface between a Blender object and an FDS namelist."""

    all = ClsList() # Re-init to obtain specific collection
    all_bf_props = ClsList()

    def __str__(self):
        return "{} > {}".format(
            str(self.element),
            self.fds_label or self.label or self.__name__,
            )

    # UI

    @classmethod
    def get_enum_item(cls) -> "List":
        """Get item for EnumProperty items."""
        return (
            cls.__name__,
            "{} ({})".format(cls.label, cls.description),
            cls.description,
            cls.enum_id
        )

    def draw_header(self, context, layout):
        """Draw Blender panel header."""
        if self.bf_prop_export:
            layout.prop(self.element, self.bf_prop_export.bpy_idname, text="")
        if self.description:
            return "FDS {} ({})".format(self.label, self.description)
        return "FDS {}".format(self.label)

    def _transform_layout(self, context, layout) -> "layout":
        """If self has a bf_prop_export, prepare Blender panel layout."""
        layout.active = self.get_exported(context)
        return layout

    def _draw_bf_props(self, context, layout):
        """Draw bf_props"""
        for bf_prop in self.bf_props or tuple():
            bf_prop.draw(context, layout)

    def draw(self, context, layout) -> "None":
        """Draw my part of Blender panel."""
        layout = self._transform_layout(context, layout)
        self._draw_messages(context, layout)
        self._draw_bf_props(context, layout)

    # Export

    def format(self, context, params):
        """Format to FDS notation."""
        # Expected output:
        # ! name: info message 1
        # ! name: info message 2
        # &OBST ID='example' XB=... /\n
        # &OBST ID='example' XB=... /\n

        # Set fds_label, if empty use first param (OP_free_namelist)
        fds_label = "".join(("&", self.fds_label or params.pop(0), " "))
        # Set info
        infos = [is_iterable(info) and info[0] or info for info in self.infos]
        info = "".join(("! {}\n".format(info) for info in infos))
        # Extract the first and only multiparams from params
        multiparams = None
        for param in params:
            if is_iterable(param):
                multiparams = param
                params.remove(param)
                # ... then remove ordinary single ID
                for param in params:
                    if param[:3] == "ID=":
                        params.remove(param)
                        break
                break
        # ... and join remaining params + namelist closure
        params.append("/\n")
        param = self.fds_separator.join(params)
        # Build namelists, set body
        # &fds_label multiparam param /
        if multiparams:
            body = "".join((
                self.fds_separator.join(("".join((fds_label, multiparam)), param)) for multiparam in multiparams
            ))
        else:
            body = "".join((fds_label, param))
        # Return
        return "".join((info, body))

    def to_fds(self, context) -> "str or None":
        """Get my exported FDS string, on error raise BFException."""
        DEBUG and print("BFDS: BFNamelist.to_fds:", str(self))
        # Check self
        if not self.get_exported(context):
            return None
        self.check(context)
        # Check and eval my bf_props
        params = list()
        errors = list()
        # Export my bf_props
        for bf_prop in self.bf_props or tuple():
            try:
                param = bf_prop.to_fds(context)
            except BFException as err:
                errors.append(err)
            else:
                if param:
                    params.append(param)
                self.infos.extend(bf_prop.infos)
        # Re-raise occurred errors
        if errors:
            raise BFException(self, "Following errors reported", errors)
        # Return
        return self.format(context, params)

    # Import

    def from_fds(self, context, tokens) -> "None":
        """Set my properties from imported FDS tokens, on error raise BFException.
        Tokens have the following format: ((fds_original, fds_label, fds_value), ...)
        Eg: {'ID': 'example', "XB": (1., 2., 3., 4., 5., 6.,), ...}
        """
        DEBUG and print("BFDS: BFNamelist.from_fds:", str(self), tokens)
        # Init
        if not tokens:
            return
        # Only scene namelists may be overwritten;
        # Do not mix old and new properties, so first set default, if it exists
        if self.bpy_type == Scene:
            self.set_default(context)
        # Treat tokens, SURF_ID needs geometry so last
        free_texts = list()
        errors = list()
        for fds_label in sorted(tokens.keys(), key=lambda k: k==("SURF_ID")):
            value, fds_value = tokens[fds_label]
            # Search managed FDS property, and import token
            bf_prop_cls = self.all_bf_props.get_by_fds_label(fds_label)
            if bf_prop_cls:
                # This FDS property is managed: instantiate and import BFProp
                try:
                    bf_prop_cls(self.element).from_fds(context, value)
                except Exception as err:
                    errors.append(err)
            else:
                # This FDS property is not managed
                free_texts.append(fds_label + "=" + fds_value)
        # Save unmanaged tokens in self.bf_prop_free
        if free_texts and self.bf_prop_free:
            self.bf_prop_free.set_value(context, " ".join(free_texts))
        # Re-raise occurred errors
        if errors:
            raise BFException(self, "Following errors reported", errors)
        # All ok, set export of myself
        self.set_exported(context, True)


#++ Specialized BFProp

class BFExportProp(BFProp):
    """This specialized BFProp is used as type for exporting properties."""
    label = "Export"
    description = "Set if exported to FDS"
    bpy_type = None  # Remember to setup!
    bpy_idname = "bf_export"
    bpy_prop = BoolProperty
    bpy_other =  {
        "default": False,
    }


class BFStringProp(BFProp):
    """This specialized BFProp is used as type for single string properties."""
    bpy_prop = StringProperty
    fds_default = ""
    bpy_type = None # Remember to setup!
    bpy_other =  {
        "maxlen": 32,
    }

    def check(self, context):
        value = self.get_value()
        if '&' in value or '/' in value:
            raise BFException(self, "& and / characters not allowed")
        if '#' in value:
            raise BFException(self, "Some special characters are not allowed (eg. #)")
        if "'" in value or '"' in value or "`" in value or "“" in value \
            or "”" in value or "‘" in value or "’‌" in value:
            raise BFException(self, "Quote characters not allowed")

    def format(self, context, value):
        if value:
            if self.fds_label:
                return "{}='{}'".format(self.fds_label, value)
            else:
                return str(value)


class BFFYIProp(BFStringProp):
    """This specialized BFProp is used as type for FYI properties."""
    label = "FYI"
    description = "Description, for your information"
    fds_label = "FYI"
    bpy_type = None # Remember to setup!
    bpy_idname = "bf_fyi"
    bpy_other =  {
        "maxlen": 128,
    }

    def _draw_body(self, context, layout):
        row = layout.row()
        row.prop(self.element, self.bpy_idname, text="", icon="INFO")


class BFFreeProp(BFStringProp):
    """This specialized BFProp is used as type for Free parameters properties."""
    label = "Free parameters"
    description = "Free parameters, use matched single quotes as string delimiters, eg <P1='example' P2=1,2,3>"
    bpy_type = None # Remember to setup!
    bpy_idname = "bf_free"
    bpy_prop = StringProperty
    bpy_other =  {
        "maxlen": 1024,
    }

    def check(self, context):
        value = self.get_value()
        if '&' in value or '/' in value:
            raise BFException(self, "& and / characters not allowed")
        if '#' in value:
            raise BFException(self, "Some special characters are not allowed (eg. #)")
        if "`" in value or "‘" in value or "’‌" in value \
            or '"' in value or "”" in value or value.count("'") % 2 != 0:
            raise BFException(self, "Only use matched single quotes as 'string' delimiters")

    def _draw_body(self, context, layout):
        row = layout.row()
        row.prop(self.element, self.bpy_idname, text="", icon="TEXT")


#++ Specialized BFProp for geometry

class BFGeometryProp(BFProp):
    """This specialized BFProp is used as type for geometric parameters properties."""
    bpy_type = Object
    bpy_prop = EnumProperty
    allowed_items = "NONE", # list of allowed items for EnumProperty

    def _transform_layout(self, context, layout):
        split = layout.split(.1)
        col1, col2 = split.row(), split.column(align=True)
        col1.label(text="{}:".format(self.label))
        return col2

    def _draw_body(self, context, layout):
        # Draw enum with allowed items only
        row = layout.row(align=True)
        for item in self.allowed_items:
            row.prop_enum(self.element, self.bpy_idname, item)


class BFXBProp(BFGeometryProp):
    """This specialized BFProp is used as type for XB parameters properties."""
    label = "XB"
    description = "XB parameter for namelist geometry"
    fds_label = "XB"
    bpy_idname = "bf_xb"


class BFXYZProp(BFGeometryProp):
    """This specialized BFProp is used as type for XYZ parameters properties."""
    label = "XYZ"
    description = "XYZ parameter for namelist geometry"
    fds_label = "XYZ"
    bpy_idname = "bf_xyz"


class BFPBProp(BFGeometryProp):
    """This specialized BFProp is used as type for PB parameters properties."""
    label = "PB*"
    description = "PB* parameter for namelist geometry"
    # fds_label = "PB" Inserted in format (like a free BFProp)
    bpy_idname = "bf_pb"


#++ Modifiers for derived BFProp

class BFNoAutoUIMod():  # No automatic UI (eg. my UI is managed elsewhere)
    def draw(self, context, layout):
        pass


class BFNoAutoExportMod():  # No automatic export (eg. my export is managed elsewhere)
    def to_fds(self, context):
        if not self.get_exported(context):
            return None
        self.check(context)


class BFNoAutoImportMod():  # No automatic import (eg. my import is managed elsewhere)
    def from_fds(self, context):
        pass


#++ Extend Blender types

class BFScene():
    """Extend Blender Scene."""

    def __str__(self):
        return "Scene {}".format(self.name)

    @classmethod
    def register(cls):
        """Register all related Blender properties."""
        DEBUG and print("BFDS: BFScene.register:", cls.__name__)
        Scene.__str__ = cls.__str__
        Scene.bf_namelists = cls.bf_namelists
        Scene.set_default_appearance = cls.set_default_appearance
        Scene._myself_to_fds = cls._myself_to_fds
        Scene._header_to_fds = cls._header_to_fds
        Scene._free_text_to_fds = cls._free_text_to_fds
        Scene._children_to_fds = cls._children_to_fds
        Scene.to_fds = cls.to_fds
        Scene.to_ge1 = cls.to_ge1
        Scene._get_imported_bf_namelist_cls = cls._get_imported_bf_namelist_cls
        Scene._get_imported_element = cls._get_imported_element
        Scene._save_imported_unmanaged_tokens = cls._save_imported_unmanaged_tokens
        Scene.from_fds = cls.from_fds

    @classmethod
    def unregister(cls):
        """Unregister all related Blender properties."""
        DEBUG and print("BFDS: BFScene.unregister:", str(cls))
        # FIXME todo

    @property
    def bf_namelists(self) -> "List of BFNamelist instances":
        """Return a list of instances of the linked Scene namelist classes."""
        bf_namelists = [
            bf_namelist(element=self)
            for bf_namelist in BFNamelist.all if bf_namelist.bpy_type == Scene
        ]
        bf_namelists.sort(key=lambda k: k.enum_id)
        return bf_namelists

    def set_default_appearance(self, context):
        self.unit_settings.system = 'METRIC'
        self.render.engine = 'CYCLES'  # for transparency visualisation

    # Export

    def _myself_to_fds(self, context) -> "list":
        """Export myself in FDS notation."""
        bodies = list()
        for bf_namelist in self.bf_namelists:
            body = bf_namelist.to_fds(context)
            if body:
                bodies.append(body)  # Could be None
        if bodies:
            bodies.append("\n")
        return bodies

    def _children_to_fds(self, context) -> "list":
        """Export children in FDS notation."""
        # Init
        bodies = list()
        # Materials
        bodies.append("\n! --- Boundary conditions (from Blender Materials)\n")
        mas = [ma for ma in bpy.data.materials]
        mas.sort(key=lambda k: k.name)  # Alphabetic order by element name
        for ma in mas:
            body = ma.to_fds(context)
            if body:
                bodies.append(body)
        # Objects
        bodies.append("\n! --- Geometric entities (from Blender Objects)\n")
        bodies.extend(Object._children_to_fds(self=None, context=context))
        # Return
        return bodies

    def _header_to_fds(self, context) -> "tuple":
        """Export header in FDS notation."""
        return (
            "! Generated by BlenderFDS {} on Blender {}\n".format(
                "{0[0]}.{0[1]}.{0[2]}".format(
                    sys.modules['zzz_blenderfds'].bl_info["version"]
                ),
                bpy.app.version_string,
            ),
            "! Case: {} (from Blender Scene)\n".format(self.name),
            "! Description: {}\n".format(self.bf_head_title),
            "! Date: {}\n".format(
                time.strftime("%a, %d %b %Y, %H:%M:%S", time.localtime())
            ),
            "! File: {}\n\n".format(bpy.data.filepath),
        )

    def _free_text_to_fds(self, context) -> "list":
        """Export HEAD free text in FDS notation."""
        bodies = list()
        # HEAD BFNnamelist traps my errors
        if self.bf_head_free_text:
            free_text = bpy.data.texts[self.bf_head_free_text].as_string()
            if not free_text:
                return bodies
            bodies.append("! --- Free text: '{}'\n".format(self.bf_head_free_text))
            bodies.append(bpy.data.texts[self.bf_head_free_text].as_string())
            if bodies[-1][-1:] != "\n":
                bodies.append("\n")
        return bodies

    def to_fds(self, context, with_children=False) -> "str or None":
        """Export myself and children (full FDS case) in FDS notation."""
        # Init
        t0 = time.time()
        bodies = list()
        # Header, Scene, free_text
        if with_children:
            bodies.extend(self._header_to_fds(context))
        bodies.extend(self._myself_to_fds(context))
        bodies.extend(self._free_text_to_fds(context))
        # Materials, objects, TAIL
        if with_children:
            bodies.extend(self._children_to_fds(context))
            bodies.append("&TAIL /\n! Generated in {0:.0f} s.".format(
                (time.time()-t0))
            )
        # Return
        return "".join(bodies)

    def to_ge1(self, context) -> "str or None":
        """Export my geometry in FDS GE1 notation."""
        return geometry.to_ge1.scene_to_ge1(context, self)

    # Import

    def _get_imported_bf_namelist_cls(
        self, context, fds_label, fds_params
    ) -> "BFNamelist or None":
        """Try to get managed BFNamelist from fds_label."""
        bf_namelist_cls = BFNamelist.all.get_by_fds_label(fds_label)
        if not bf_namelist_cls:
            if any(
                (label in fds_params
                    for label in ('XB', 'XYZ', 'PBX', 'PBY', 'PBZ'))
            ):
                # An unmanaged geometric namelist
                bf_namelist_cls = BFNamelist.all["ON_free"]
        return bf_namelist_cls

    def _get_imported_element(
        self, context, bf_namelist_cls, fds_label
    ) -> "Element":
        """Get element."""
        bpy_type = bf_namelist_cls.bpy_type
        if bpy_type == bpy.types.Scene:
            element = self  # Import into self
        elif bpy_type == bpy.types.Object:
            element = geometry.utils.get_new_object(
                context, self, name="New {}".format(fds_label)
            )  # New Object
            # Set link to namelist
            element.bf_namelist_cls = bf_namelist_cls.__name__
        elif bpy_type == bpy.types.Material:
            element = geometry.utils.get_new_material(
                context, name="New {}".format(fds_label)
            )  # New Material
            element.bf_namelist_cls = "MN_SURF"  # Set link to default namelist
        else:
            raise ValueError(
                "BFDS: BFScene.from_fds: Unrecognized namelist type!"
            )
        element.set_default_appearance(context)
        return element

    def _save_imported_unmanaged_tokens(self, context, free_texts) -> "None":
        """Save unmanaged tokens to free text."""
        # Get or create free text file, then show
        bf_head_free_text = fds.head.set_free_text_file(context, self)
        # Get existing contents
        old_free_texts = bpy.data.texts[bf_head_free_text].as_string()
        if old_free_texts:
            free_texts.append(old_free_texts)
        # Write merged contents
        bpy.data.texts[bf_head_free_text].from_string("\n".join(free_texts))

    def from_fds(self, context, value):
        """Import a text in FDS notation into self."""
        tokens = None
        errors = False
        free_texts = list()
        # Tokenize value and manage exception
        try:
            tokens = fds.to_py.tokenize(value)
        except BFException as err:
            errors = True
            free_texts.extend(err.free_texts)  # Record in free_texts
        # Treat tokens, first SURFs
        if tokens:
            for token in sorted(tokens, key=lambda k: k[0] != ("SURF_ID")):
                # Init
                fds_label, fds_params, fds_original = token
                # Search managed FDS namelist, and import token
                bf_namelist_cls = self._get_imported_bf_namelist_cls(
                    context, fds_label, fds_params)
                if bf_namelist_cls:
                    # This FDS namelists is managed:
                    # get element, instanciate and import BFNamelist
                    element = self._get_imported_element(
                        context, bf_namelist_cls, fds_label)
                    try:
                        bf_namelist_cls(element).from_fds(context, fds_params)
                    except BFException as err:
                        errors = True
                        free_texts.extend(err.free_texts)
                else:
                    # This FDS namelists is not managed
                    free_texts.append(fds_original)
        # Save free_texts, even if empty
        # (remember, bf_head_free_text is not set to default)
        self._save_imported_unmanaged_tokens(context, free_texts)
        # Return
        if errors:
            raise BFException(
                self, "Errors reported, see details in HEAD free text file.")


class BFObject():
    """Extend Blender Object."""

    def __str__(self):
        return "Object {}".format(self.name)

    @classmethod
    def register(cls):
        """Register all related Blender properties."""
        DEBUG and print("BFDS: BFObject.register:", cls.__name__)
        Object.__str__ = cls.__str__
        Object.bf_namelist = cls.bf_namelist
        Object.set_default_appearance = cls.set_default_appearance
        Object._myself_to_fds = cls._myself_to_fds
        Object._children_to_fds = cls._children_to_fds
        Object.to_fds = cls.to_fds
        Object.set_tmp = cls.set_tmp
        Object.show_tmp_obs = cls.show_tmp_obs
        Object.remove_tmp_obs = cls.remove_tmp_obs

    @classmethod
    def unregister(cls):
        """Unregister all related Blender properties."""
        DEBUG and print("BFDS: BFObject.unregister:", str(cls)) # TODO unregister
        del cls.__str__
        del cls.bf_namelist

    @property
    def bf_namelist(self) -> "BFNamelist instance or None":
        """Return an instance of the linked Object namelist class."""
        # ~ if self.type != "MESH" or self.bf_is_tmp:
            # ~ return None
        ON_cls = BFNamelist.all.get(self.bf_namelist_cls)
        if ON_cls:
            return ON_cls(element=self)  # create instance from class

    def set_default_appearance(self, context):
        """Set default object appearance."""
        # Get bf_namelist
        bf_namelist = self.bf_namelist
        if not bf_namelist:
            return
        # Set draw_type
        draw_type = bf_namelist.bf_other.get("draw_type")
        if draw_type:
            self.draw_type = draw_type
        # Set show_transparent
        self.show_transparent = True

    # Export to FDS

    def _myself_to_fds(self, context) -> "list":
        """Export myself in FDS notation."""
        bodies = list()
        if self.bf_export:
            if self.type == "MESH":
                bf_namelist = self.bf_namelist
                if bf_namelist:
                    body = bf_namelist.to_fds(context)
                    if body:
                        bodies.append(body)  # could be None
            elif self.type == "EMPTY":
                bodies.append("! -- {}: {}\n".format(self.name, self.bf_fyi))
        return bodies

    def _children_to_fds(self, context) -> "list":
        """Export children in FDS notation."""
        # Init
        children_obs = [ob for ob in context.scene.objects if ob.parent == self]
        children_obs.sort(key=lambda k: k.name)  # Order by element name
        children_obs.sort(key=lambda k: k.bf_namelist_cls != ("ON_MESH"))
        # Children to_fds
        bodies = list()
        for ob in children_obs:
            body = ob.to_fds(context, with_children=True)
            if body:
                bodies.append(body)  # could be None
        if bodies:
            bodies.append("\n")
        # Return
        return bodies

    def to_fds(self, context, with_children=False, max_lines=0) -> "str or None":
        """Export myself and children in FDS notation."""
        bodies = list()
        bodies.extend(self._myself_to_fds(context))
        if with_children:
            bodies.extend(self._children_to_fds(context))
        return "".join(bodies)

    # Manage tmp objects

    def set_tmp(self, context, ob):
        """Set self as temporary object of ob."""
        # Link object to context scene
        # context.scene.objects.link(self) # TODO Is it always already linked?
        # Set temporary object
        self.bf_is_tmp = True
        self.active_material = ob.active_material
        self.layers = ob.layers
        # self.groups = ob.groups TODO does not work but would be useful!
        self.show_wire = True
        # Set parenting and keep position
        self.parent = ob
        self.matrix_parent_inverse = ob.matrix_world.inverted()
        # Set parent object
        ob.bf_has_tmp = True

    def show_tmp_obs(self, context):
        """Show my temporary objects."""
        # Show my tmp obs
        for child in self.children:
            if child.bf_is_tmp:
                child.hide = False
        # Set myself hidden but active
        self.select = True
        context.scene.objects.active = self
        self.hide = True

    def remove_tmp_obs(self, context):
        """Remove my temporary objects."""
        # Remove my tmp obs
        for child in self.children:
            if child.bf_is_tmp:
                bpy.data.objects.remove(child, do_unlink=True)
        self.bf_has_tmp = False
        # Set myself visible
        self.hide = False


class BFMaterial():
    """Extend Blender Material."""

    def __str__(self):
        return "Material {}".format(self.name)

    @classmethod
    def register(cls):
        """Register all related Blender properties."""
        DEBUG and print("BFDS: BFMaterial.register:", cls.__name__)
        Material.__str__ = cls.__str__
        Material.bf_namelist = cls.bf_namelist
        Material.set_default_appearance = cls.set_default_appearance
        Material.to_fds = cls.to_fds

    @classmethod
    def unregister(cls):
        """Unregister all related Blender properties."""
        DEBUG and print("BFDS: BFMaterial.unregister:", str(cls))
        del cls.__str__
        del cls.bf_namelist

    @property
    def bf_namelist(self) -> "BFNamelist instance or None":
        """Return an instance of the linked Material namelist class."""
        MN_cls = BFNamelist.all.get(self.bf_namelist_cls)
        if MN_cls:
            return MN_cls(element=self)  # create instance from class

    def set_default_appearance(self, context):
        """Set default material appearance."""
        self.use_fake_user = True

    def to_fds(self, context) -> "str or None":
        """Export myself in FDS notation."""
        if self.name not in fds.surf.predefined:
            bf_namelist = self.bf_namelist
            if bf_namelist:
                return bf_namelist.to_fds(context)
