from opcua import ua

import xml.etree.ElementTree as Et
import re

ROS_BUILD_IN_DATA_TYPES = {'bool': ua.VariantType.Boolean,
                           'int8': ua.VariantType.SByte,
                           'byte': ua.VariantType.SByte,  # deprecated int8
                           'uint8': ua.VariantType.Byte,
                           'char': ua.VariantType.Byte,  # deprecated uint8
                           'int16': ua.VariantType.Int16,
                           'uint16': ua.VariantType.UInt16,
                           'int32': ua.VariantType.Int32,
                           'uint32': ua.VariantType.UInt32,
                           'int64': ua.VariantType.Int64,
                           'uint64': ua.VariantType.UInt64,
                           'float32': ua.VariantType.Float,
                           'float64': ua.VariantType.Float,
                           'string': ua.VariantType.String,
                           'time': ua.VariantType.DateTime,
                           'duration': ua.VariantType.DateTime}

UA_BASIC_TYPES = [item.name for item in ROS_BUILD_IN_DATA_TYPES.values()]


def ua_class_to_ros_msg(ua_class, ros_msg):
    # deal with method with empty parameters
    if not ua_class:
        return None
    for attr in ua_class.ua_types:
        if attr[1] in UA_BASIC_TYPES:
            setattr(ros_msg, attr[0], getattr(ua_class, attr[0]))
        else:
            ua_class_to_ros_msg(getattr(ua_class, attr[0]), getattr(ros_msg, attr[0]))
    return ros_msg


def ros_msg_to_ua_class(ros_msg, ua_class):
    # BUG: To deal with bug (BadEndOfStream) in calling methods with empty extension objects
    if not len(ros_msg.__slots__):
        return None
    for attr, data_type in zip(ros_msg.__slots__, getattr(ros_msg, '_slot_types')):
        if data_type in ROS_BUILD_IN_DATA_TYPES.keys():
            setattr(ua_class, attr, getattr(ros_msg, attr))
        else:
            ros_msg_to_ua_class(getattr(ros_msg, attr), getattr(ua_class, attr))
    return ua_class


def nodeid_generator(idx):
    return ua.NodeId(namespaceidx=idx)


def create_args(msg_class, data_type):
    """one extension object contains all info"""
    if not len(getattr(msg_class, '__slots__')):
        return []
    msg_class_name = getattr(msg_class, '_type')
    arg = ua.Argument()
    arg.Name = msg_class_name
    arg.DataType = data_type
    arg.ValueRank = -1
    arg.ArrayDimensions = []
    arg.Description = ua.LocalizedText(msg_class_name)
    return [arg]


def _repl_func(m):
    """
    taken from
     https://stackoverflow.com/questions/1549641/how-to-capitalize-the-first-letter-of-each-word-in-a-string-python
     """
    return m.group(1) + m.group(2).upper()


def to_camel_case(name):
    """
    Create python class name from an arbitrary string to CamelCase string
    e.g.                 actionlib/TestAction -> ActionlibTestAction
         turtle_actionlib/ShapeActionFeedback -> TurtleActionlibShapeActionFeedback
    """
    name = re.sub(r'[^a-zA-Z0-9]+', ' ', name)
    name = re.sub('(^|\s)(\S)', _repl_func, name)
    name = re.sub(r'[^a-zA-Z0-9]+', '', name)
    return name


class OPCTypeDictionaryBuilder:

    def __init__(self, idx_name, build_in_dict):
        """
        :param idx_name: name of the name space
        :param build_in_dict: indicates which type should be build in types,
        types in dict is created as opc:xxx, otherwise as tns:xxx
        """
        head_attributes = {'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance', 'xmlns:tns': idx_name,
                           'DefaultByteOrder': 'LittleEndian', 'xmlns:opc': 'http://opcfoundation.org/BinarySchema/',
                           'xmlns:ua': 'http://opcfoundation.org/UA/', 'TargetNamespace': idx_name}

        self.etree = Et.ElementTree(Et.Element('opc:TypeDictionary', head_attributes))

        name_space = Et.SubElement(self.etree.getroot(), 'opc:Import')
        name_space.attrib['Namespace'] = 'http://opcfoundation.org/UA/'

        self._structs_dict = {}
        self._build_in_dict = build_in_dict

    def _add_field(self, type_name, variable_name, struct_name):
        if type_name in self._build_in_dict:
            type_name = 'opc:' + getattr(self._build_in_dict[type_name], '_name_')
        else:
            type_name = 'tns:' + to_camel_case(type_name)
        field = Et.SubElement(self._structs_dict[struct_name], 'opc:Field')
        field.attrib['Name'] = variable_name
        field.attrib['TypeName'] = type_name

    def _add_array_field(self, type_name, variable_name, struct_name):
        if type_name in self._build_in_dict:
            type_name = 'opc:' + getattr(self._build_in_dict[type_name], '_name_')
        else:
            type_name = 'tns:' + to_camel_case(type_name)
        array_len = 'NoOf' + variable_name
        field = Et.SubElement(self._structs_dict[struct_name], 'opc:Field')
        field.attrib['Name'] = array_len
        field.attrib['TypeName'] = 'opc:Int32'
        field = Et.SubElement(self._structs_dict[struct_name], 'opc:Field')
        field.attrib['Name'] = variable_name
        field.attrib['TypeName'] = type_name
        field.attrib['LengthField'] = array_len

    def add_field(self, type_name, variable_name, struct_name, is_array=False):
        if is_array:
            self._add_array_field(type_name, variable_name, struct_name)
        else:
            self._add_field(type_name, variable_name, struct_name)

    def append_struct(self, name):
        appended_struct = Et.SubElement(self.etree.getroot(), 'opc:StructuredType')
        appended_struct.attrib['BaseType'] = 'ua:ExtensionObject'
        appended_struct.attrib['Name'] = to_camel_case(name)
        self._structs_dict[name] = appended_struct
        return appended_struct

    def get_dict_value(self):
        self.indent(self.etree.getroot())
        # For debugging
        # Et.dump(self.etree.getroot())
        return Et.tostring(self.etree.getroot(), encoding='utf-8')

    def indent(self, elem, level=0):
        i = '\n' + level * '  '
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + '  '
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self.indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i


class DataTypeDictionaryBuilder:

    def __init__(self, server, idx, idx_name, dict_name):
        self._server = server
        self._session_server = server.get_root_node().server
        self._idx = idx
        # Risk of bugs using a fixed number without checking
        self._id_counter = 8000
        self.dict_id = self._add_dictionary(dict_name)

        self._type_dictionary = OPCTypeDictionaryBuilder(idx_name, ROS_BUILD_IN_DATA_TYPES)

    def nodeid_generator(self):
        self._id_counter += 1
        return ua.NodeId(self._id_counter, namespaceidx=self._idx, nodeidtype=ua.NodeIdType.Numeric)

    def _add_dictionary(self, name):
        dictionary_node_id = self.nodeid_generator()
        node = ua.AddNodesItem()
        node.RequestedNewNodeId = dictionary_node_id
        node.BrowseName = ua.QualifiedName(name, self._idx)
        node.NodeClass = ua.NodeClass.Variable
        node.ParentNodeId = ua.NodeId(ua.ObjectIds.OPCBinarySchema_TypeSystem, 0)
        node.ReferenceTypeId = ua.NodeId(ua.ObjectIds.HasComponent, 0)
        node.TypeDefinition = ua.NodeId(ua.ObjectIds.DataTypeDictionaryType, 0)
        attrs = ua.VariableAttributes()
        attrs.DisplayName = ua.LocalizedText(name)
        attrs.DataType = ua.NodeId(ua.ObjectIds.ByteString)
        # Value should be set after all data types created by calling set_dict_byte_string
        attrs.Value = ua.Variant(None, ua.VariantType.Null)
        attrs.ValueRank = -1
        node.NodeAttributes = attrs
        self._session_server.add_nodes([node])

        return dictionary_node_id

    @staticmethod
    def _reference_generator(source_id, target_id, reference_type, is_forward=True):
        ref = ua.AddReferencesItem()
        ref.IsForward = is_forward
        ref.ReferenceTypeId = reference_type
        ref.SourceNodeId = source_id
        ref.TargetNodeClass = ua.NodeClass.DataType
        ref.TargetNodeId = target_id
        return ref

    def _link_nodes(self, linked_obj_node_id, data_type_node_id, description_node_id):
        """link the three node by their node ids according to UA standard"""
        refs = [
                # add reverse reference to BaseDataType -> Structure0
                self._reference_generator(data_type_node_id, ua.NodeId(ua.ObjectIds.Structure, 0),
                                          ua.NodeId(ua.ObjectIds.HasSubtype, 0), False),
                # add reverse reference to created data type
                self._reference_generator(linked_obj_node_id, data_type_node_id,
                                          ua.NodeId(ua.ObjectIds.HasEncoding, 0), False),
                # add HasDescription link to dictionary description
                self._reference_generator(linked_obj_node_id, description_node_id,
                                          ua.NodeId(ua.ObjectIds.HasDescription, 0)),
                # add reverse HasDescription link
                self._reference_generator(description_node_id, linked_obj_node_id,
                                          ua.NodeId(ua.ObjectIds.HasDescription, 0), False),
                # add link to the type definition node
                self._reference_generator(linked_obj_node_id, ua.NodeId(ua.ObjectIds.DataTypeEncodingType, 0),
                                          ua.NodeId(ua.ObjectIds.HasTypeDefinition, 0)),
                # add has type definition link
                self._reference_generator(description_node_id, ua.NodeId(ua.ObjectIds.DataTypeDescriptionType, 0),
                                          ua.NodeId(ua.ObjectIds.HasTypeDefinition, 0)),
                # forward link of dict to description item
                self._reference_generator(self.dict_id, description_node_id,
                                          ua.NodeId(ua.ObjectIds.HasComponent, 0)),
                # add reverse link to dictionary
                self._reference_generator(description_node_id, self.dict_id,
                                          ua.NodeId(ua.ObjectIds.HasComponent, 0), False)]
        self._session_server.add_references(refs)

    def create_data_type(self, type_name):
        name = to_camel_case(type_name)
        # apply for new node id
        data_type_node_id = self.nodeid_generator()
        description_node_id = self.nodeid_generator()
        bind_obj_node_id = self.nodeid_generator()

        # create data type node
        dt_node = ua.AddNodesItem()
        dt_node.RequestedNewNodeId = data_type_node_id
        dt_node.BrowseName = ua.QualifiedName(name, self._idx)
        dt_node.NodeClass = ua.NodeClass.DataType
        dt_node.ParentNodeId = ua.NodeId(ua.ObjectIds.Structure, 0)
        dt_node.ReferenceTypeId = ua.NodeId(ua.ObjectIds.HasSubtype, 0)
        dt_attributes = ua.DataTypeAttributes()
        dt_attributes.DisplayName = ua.LocalizedText(type_name)
        dt_node.NodeAttributes = dt_attributes

        # create description node
        desc_node = ua.AddNodesItem()
        desc_node.RequestedNewNodeId = description_node_id
        desc_node.BrowseName = ua.QualifiedName(name, self._idx)
        desc_node.NodeClass = ua.NodeClass.Variable
        desc_node.ParentNodeId = self.dict_id
        desc_node.ReferenceTypeId = ua.NodeId(ua.ObjectIds.HasComponent, 0)
        desc_node.TypeDefinition = ua.NodeId(ua.ObjectIds.DataTypeDescriptionType, 0)
        desc_attributes = ua.VariableAttributes()
        desc_attributes.DisplayName = ua.LocalizedText(type_name)
        desc_attributes.DataType = ua.NodeId(ua.ObjectIds.String)
        desc_attributes.Value = ua.Variant(name, ua.VariantType.String)
        desc_attributes.ValueRank = -1
        desc_node.NodeAttributes = desc_attributes

        # create object node python class should link to
        obj_node = ua.AddNodesItem()
        obj_node.RequestedNewNodeId = bind_obj_node_id
        obj_node.BrowseName = ua.QualifiedName('Default Binary', 0)
        obj_node.NodeClass = ua.NodeClass.Object
        obj_node.ParentNodeId = data_type_node_id
        obj_node.ReferenceTypeId = ua.NodeId(ua.ObjectIds.HasEncoding, 0)
        obj_node.TypeDefinition = ua.NodeId(ua.ObjectIds.DataTypeEncodingType, 0)
        obj_attributes = ua.ObjectAttributes()
        obj_attributes.DisplayName = ua.LocalizedText('Default Binary')
        obj_attributes.EventNotifier = 0
        obj_node.NodeAttributes = obj_attributes

        self._session_server.add_nodes([dt_node, desc_node, obj_node])
        self._link_nodes(bind_obj_node_id, data_type_node_id, description_node_id)

        self._type_dictionary.append_struct(type_name)

        return data_type_node_id

    def add_field(self, type_name, variable_name, struct_name, is_array=False):
        self._type_dictionary.add_field(type_name, variable_name, struct_name, is_array)

    def set_dict_byte_string(self):
        dict_node = self._server.get_node(self.dict_id)
        value = self._type_dictionary.get_dict_value()
        dict_node.set_value(value, ua.VariantType.ByteString)


def get_ua_class(ua_class_name):
    return getattr(ua, to_camel_case(ua_class_name))
