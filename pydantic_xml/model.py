from typing import Any, ClassVar, Dict, Optional, Tuple, Type, Union

import pydantic as pd
import pydantic.fields
import pydantic.generics

from . import config, errors, serializers
from .backend import etree
from .utils import NsMap, register_nsmap


class XmlEntityInfo(pd.fields.FieldInfo):
    """
    Field xml meta-information.
    """


class XmlAttributeInfo(XmlEntityInfo):
    """
    Field xml attribute meta-information.

    :param tag: attribute name
    :param ns: attribute xml namespace
    :param kwargs: pydantic field arguments
    """

    def __init__(
            self,
            name: Optional[str] = None,
            ns: Optional[str] = None,
            **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._name = name
        self._ns = ns

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def ns(self) -> Optional[str]:
        return self._ns


class XmlElementInfo(XmlEntityInfo):
    """
    Field xml element meta-information.

    :param tag: element tag
    :param ns: element xml namespace
    :param nsmap: element xml namespace map
    :param kwargs: pydantic field arguments
    """

    def __init__(
            self,
            tag: Optional[str] = None,
            ns: Optional[str] = None,
            nsmap: Optional[NsMap] = None,
            **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._tag = tag
        self._ns = ns
        self._nsmap = nsmap

        if config.REGISTER_NS_PREFIXES and nsmap:
            register_nsmap(nsmap)

    @property
    def tag(self) -> Optional[str]:
        return self._tag

    @property
    def ns(self) -> Optional[str]:
        return self._ns

    @property
    def nsmap(self) -> Optional[NsMap]:
        return self._nsmap


class XmlWrapperInfo(XmlEntityInfo):
    """
    Field xml wrapper meta-information.

    :param entity: wrapped entity
    :param tag: element tag
    :param ns: element xml namespace
    :param nsmap: element xml namespace map
    :param kwargs: pydantic field arguments
    """

    def __init__(
            self,
            path: str,
            entity: Optional[XmlEntityInfo] = None,
            ns: Optional[str] = None,
            nsmap: Optional[NsMap] = None,
            **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._entity = entity
        self._path = path
        self._ns = ns
        self._nsmap = nsmap

        if config.REGISTER_NS_PREFIXES and nsmap:
            register_nsmap(nsmap)

    @property
    def entity(self) -> Optional[XmlEntityInfo]:
        return self._entity

    @property
    def path(self) -> str:
        return self._path

    @property
    def ns(self) -> Optional[str]:
        return self._ns

    @property
    def nsmap(self) -> Optional[NsMap]:
        return self._nsmap


def attr(**kwargs: Any) -> XmlAttributeInfo:
    """
    Marks a pydantic field as an xml attribute.
    """

    return XmlAttributeInfo(**kwargs)


def element(**kwargs: Any) -> XmlElementInfo:
    """
    Marks a pydantic field as an xml element.
    """

    return XmlElementInfo(**kwargs)


def wrapped(*args: Any, **kwargs: Any) -> XmlWrapperInfo:
    """
    Marks a pydantic field as a wrapped xml entity.
    """

    return XmlWrapperInfo(*args, **kwargs)


class XmlModelMeta(pd.main.ModelMetaclass):

    __is_base_model_defined__ = False

    def __new__(mcls, name: str, bases: Tuple[type], namespace: Dict[str, Any], **kwargs: Any) -> Type['BaseXmlModel']:
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        if mcls.__is_base_model_defined__:
            cls.__init_serializer__()
        else:
            mcls.__is_base_model_defined__ = True

        return cls


class BaseXmlModel(pd.BaseModel, metaclass=XmlModelMeta):
    """
    Base pydantic-xml model.
    """

    __xml_tag__: ClassVar[Optional[str]]
    __xml_ns__: ClassVar[Optional[str]]
    __xml_nsmap__: ClassVar[Optional[NsMap]]
    __xml_ns_attrs__: ClassVar[bool]
    __xml_serializer__: ClassVar[Optional[serializers.ModelSerializerFactory.RootSerializer]]

    def __init_subclass__(
            cls,
            *args: Any,
            tag: Optional[str] = None,
            ns: Optional[str] = None,
            nsmap: Optional[NsMap] = None,
            ns_attrs: bool = False,
            **kwargs: Any,
    ):
        """
        Initializes a subclass.

        :param tag: element tag
        :param ns: element namespace
        :param nsmap: element namespace map
        :param ns_attrs: use namespaced attributes
        """

        super().__init_subclass__(*args, **kwargs)

        cls.__xml_tag__ = tag
        cls.__xml_ns__ = ns
        cls.__xml_nsmap__ = nsmap
        cls.__xml_ns_attrs__ = ns_attrs

    @classmethod
    def __init_serializer__(cls) -> None:
        if config.REGISTER_NS_PREFIXES and cls.__xml_nsmap__:
            register_nsmap(cls.__xml_nsmap__)

        cls.__xml_serializer__ = serializers.ModelSerializerFactory.from_model(cls)

    @classmethod
    def from_xml_tree(cls, root: etree.Element) -> 'BaseXmlModel':
        """
        Deserializes an xml element tree to an object of `cls` type.

        :param root: xml element to deserialize the object from
        :return: deserialized object
        """

        assert cls.__xml_serializer__ is not None, "model is partially initialized"
        obj = cls.__xml_serializer__.deserialize(root)

        return cls.parse_obj(obj)

    @classmethod
    def from_xml(cls, source: Union[str, bytes]) -> 'BaseXmlModel':
        """
        Deserializes an xml string to an object of `cls` type.

        :param source: xml string
        :return: deserialized object
        """

        return cls.from_xml_tree(etree.fromstring(source))

    def to_xml_tree(
            self,
            *,
            encoder: Optional[serializers.XmlEncoder] = None,
            skip_empty: bool = False,
    ) -> etree.Element:
        """
        Serializes the object to an xml tree.

        :param encoder: xml type encoder
        :param skip_empty: skip empty elements (elements without sub-elements, attributes and text, Nones)
        :return: object xml representation
        """

        encoder = encoder or serializers.DEFAULT_ENCODER

        assert self.__xml_serializer__ is not None
        root = self.__xml_serializer__.serialize(None, self, encoder=encoder, skip_empty=skip_empty)
        assert root is not None

        if self.__xml_nsmap__ and (default_ns := self.__xml_nsmap__.get('')):
            root.set('xmlns', default_ns)

        return root

    def to_xml(
            self,
            *,
            encoder: Optional[serializers.XmlEncoder] = None,
            skip_empty: bool = False,
            **kwargs: Any,
    ) -> Union[str, bytes]:
        """
        Serializes the object to an xml string.

        :param encoder: xml type encoder
        :param skip_empty: skip empty elements (elements without sub-elements, attributes and text, Nones)
        :param kwargs: additional xml serialization arguments
        :return: object xml representation
        """

        return etree.tostring(self.to_xml_tree(encoder=encoder, skip_empty=skip_empty), **kwargs)


class BaseGenericXmlModel(BaseXmlModel, pd.generics.GenericModel):
    """
    Base pydantic-xml generic model.
    """

    def __class_getitem__(cls, params: Union[Type[Any], Tuple[Type[Any], ...]]) -> Type[Any]:
        model = super().__class_getitem__(params)
        model.__xml_tag__ = cls.__xml_tag__
        model.__xml_ns__ = cls.__xml_ns__
        model.__xml_nsmap__ = cls.__xml_nsmap__
        model.__xml_ns_attrs__ = cls.__xml_ns_attrs__
        model.__init_serializer__()

        return model

    @classmethod
    def __init_serializer__(cls) -> None:
        # checks that the model is not generic
        if not getattr(cls, '__concrete__', True):
            cls.__xml_serializer__ = None
        else:
            super().__init_serializer__()

    @classmethod
    def from_xml_tree(cls, root: etree.Element) -> 'BaseXmlModel':
        """
        Deserializes an xml element tree to an object of `cls` type.

        :param root: xml element to deserialize the object from
        :return: deserialized object
        """

        if cls.__xml_serializer__ is None:
            raise errors.ModelError(f"{cls.__name__} model is generic")

        return super().from_xml_tree(root)
