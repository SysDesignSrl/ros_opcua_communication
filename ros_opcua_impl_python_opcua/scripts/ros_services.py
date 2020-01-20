#!/usr/bin/env python

# Thanks to:
# https://github.com/ros-visualization/rqt_common_plugins/blob/groovy-devel/rqt_service_caller/src/rqt_service_caller/service_caller_widget.py
import math
import random
import time

import rospy
import genpy
import roslib
import rosservice
from opcua import ua, uamethod, common

import ros_server
import ros_utils


def refresh_dict(ros_namespace, ros_server, services_dict, idx):
    # get current provided services
    ros_services = rosservice.get_service_list()

    to_be_deleted = []
    for node_name in services_dict:
        #
        found = False
        for service_name in ros_services:
            if node_name == service_name:
                found = True
        #
        if not found and services_dict[node_name] is not None:
            services_dict[node_name].recursive_delete_nodes(ros_server.server.get_node(ua.NodeId(node_name, idx)))
            to_be_deleted.append(node_name)
        #
        if len(services_dict[node_name].parent.get_children()) == 0:
            ros_server.server.delete_nodes([services_dict[node_name].parent])

    for node_name in to_be_deleted:
        del services_dict[node_name]


def refresh_services(ros_namespace, ros_server, services_dict, idx, services_object):
    ros_services = rosservice.get_service_list(namespace=ros_namespace)

    for service_name in ros_services:
        try:
            if service_name not in services_dict or services_dict[service_name] is None:
                opcua_service = OpcUaROSService(ros_server, services_object, idx, service_name, rosservice.get_service_type(service_name))
                services_dict[service_name] = opcua_service
        except (rosservice.ROSServiceException, rosservice.ROSServiceIOException) as ex:
            try:
                rospy.logerr("Error when trying to refresh services", ex)
            except TypeError as e2:
                rospy.logerr("Error when logging an Exception, can't convert everything to string")

    refresh_dict(ros_namespace, ros_server, services_dict, idx)


def get_arg_array(req):
    array = []
    for slot_name, slot_type in zip(req.__slots__, req._slot_types):
        rospy.logdebug("converting slot name: '%s' with type: '%s'", slot_name, slot_type)
        slot_value = getattr(req, slot_name)
        if hasattr(slot_value, '_type'):
            array_to_merge = get_arg_array(slot_value)
            array.extend(array_to_merge)
        else:
            arg = get_arg_from_slot(slot_name, slot_type)
            array.append(arg)

            # if isinstance(slot, list):
            #     arg = ua.Argument()
            #     arg.Name = slot_name
            #     arg.DataType = ua.NodeId(get_object_id_from_type(type(slot).__name__))
            #     arg.ValueRank = 1
            #     arg.ArrayDimensions = [0]
            #     arg.Description = ua.LocalizedText(slot_name)
            # else:
            #     arg = ua.Argument()
            #     arg.Name = slot_name
            #     arg.DataType = ua.NodeId(get_object_id_from_type(type(slot).__name__))
            #     arg.ValueRank = -1
            #     arg.ArrayDimensions = []
            #     arg.Description = ua.LocalizedText(slot_name)
            # array.append(arg)

    return array


def get_arg_from_slot(slot_name, slot_type):

    type_str, array_size = extract_array_info(slot_type)

    arg = ua.Argument()
    arg.Name = slot_name
    arg.Description = ua.LocalizedText(slot_name)

    if type_str == 'bool':
        arg.DataType = ua.NodeId(ua.ObjectIds.Boolean, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'int8':
        arg.DataType = ua.NodeId(ua.ObjectIds.SByte, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'byte' or type_str == 'uint8':
        arg.DataType = ua.NodeId(ua.ObjectIds.Byte, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'int16':
        rospy.roswarn("Int16??")
        arg.DataType = ua.NodeId(ua.ObjectIds.Int16, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'uint16':
        arg.DataType = ua.NodeId(ua.ObjectIds.UInt16, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'int' or type_str == 'int32':
        arg.DataType = ua.NodeId(ua.ObjectIds.Int32, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'uint32':
        arg.DataType = ua.NodeId(ua.ObjectIds.UInt32, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'int64':
        arg.DataType = ua.NodeId(ua.ObjectIds.Int64, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'uint64':
        arg.DataType = ua.NodeId(ua.ObjectIds.UInt64, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'float' or type_str == 'float32' or type_str == 'float64':
        arg.DataType = ua.NodeId(ua.ObjectIds.Float, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'double':
        arg.DataType = ua.NodeId(ua.ObjectIds.Double, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'string':
        arg.DataType = ua.NodeId(ua.ObjectIds.String, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    elif type_str == 'Time' or type_str == 'time':
        arg.DataType = ua.NodeId(ua.ObjectIds.Time, 0)
        arg.ValueRank = -1 if array_size is None else 0
        arg.ArrayDimensions = [] if array_size is None else [array_size]
    else:
        rospy.logerr("Can't create type with name " + slot_type)
        return None

    return arg


class OpcUaROSService:

    def __init__(self, ros_server, parent, idx, service_name, service_type):
        self.server = ros_server
        self.parent = parent # self.recursive_create_objects(service_name, idx, parent)
        self.idx = idx

        self.service_name = service_name
        self.service_type = service_type
        rospy.logdebug("service_name: '%s'", self.service_name)
        rospy.logdebug("service_type: '%s'", self.service_type)

        self.counter = 0
        self._nodes = {}
        self.expressions = {}
        self._eval_locals = {}

        try:
            self.srv_class = rosservice.get_service_class_by_name(self.service_name)
            self.srv_instance = self.srv_class()
        except rospy.ROSException:
            rospy.logfatal("Couldn't find service class for type '%s'", self.service_type)
            return

        self.proxy = rospy.ServiceProxy(self.service_name, rosservice.get_service_class_by_name(self.service_name))


        # for module in (math, random, time):
        #     self._eval_locals.update(module.__dict__)
        #
        # self._eval_locals['genpy'] = genpy
        # del self._eval_locals['__name__']
        # del self._eval_locals['__doc__']

        # Build the Array of inputs
        # self.srv_class_req = self.srv_class._request_class()
        # self.srv_class_res = self.srv_class._response_class()
        self.inputs  = get_arg_array(self.srv_class._request_class())
        self.outputs = get_arg_array(self.srv_class._response_class())
        self.method = self.parent.add_method(idx, self.service_name, self.call_service, self.inputs, self.outputs)

        rospy.loginfo("Created ROS Service: %s", self.service_name)


    def recursive_create_objects(self, name, idx, parent):
        hierachy = name.split('/')
        if len(hierachy) == 0 or len(hierachy) == 1:
            return parent
        for name in hierachy:
            if name != '':
                try:
                    nodewithsamename = self.server.find_service_node_with_same_name(name, idx)
                    rospy.logdebug("nodewithsamename for name: " + str(name) + " is : " + str(nodewithsamename))
                    if nodewithsamename is not None:
                        rospy.logdebug("recursive call for same name for: " + name)
                        return self.recursive_create_objects(ros_server.nextname(hierachy, hierachy.index(name)), idx,
                                                             nodewithsamename)
                    else:
                        newparent = parent.add_object(
                            ua.NodeId(name, parent.nodeid.NamespaceIndex, ua.NodeIdType.String),
                            ua.QualifiedName(name, parent.nodeid.NamespaceIndex))
                        return self.recursive_create_objects(ros_server.nextname(hierachy, hierachy.index(name)), idx,
                                                             newparent)
                except IndexError, common.uaerrors.UaError:
                    newparent = parent.add_object(
                        ua.NodeId(name + str(random.randint(0, 10000)), parent.nodeid.NamespaceIndex,
                                  ua.NodeIdType.String),
                        ua.QualifiedName(name, parent.nodeid.NamespaceIndex))
                    return self.recursive_create_objects(ros_server.nextname(hierachy, hierachy.index(name)), idx,
                                                         newparent)
        return parent


    @uamethod
    def call_service(self, parent, *inputs):
        try:
            rospy.loginfo("Calling Service with name: " + self.name)
            input_msg = self.create_message_instance(inputs, self.sample_req)
            rospy.logdebug("Created Input Request for Service " + self.name + " : " + str(input_msg))
            response = self.proxy(input_msg)

            rospy.logdebug("Got response: " + str(response))
            rospy.logdebug("Creating response message object")
            return_values = ros_msg_to_flat_values(response)

            rospy.logdebug("Current Response list: " + str(return_values))
            return return_values
        except (TypeError, rospy.ROSException, rospy.ROSInternalException, rospy.ROSSerializationException,
                common.uaerrors.UaError, rosservice.ROSServiceException) as ex:
            rospy.logerr("Error when calling service " + self.name, ex)


    def create_message_instance(self, inputs, sample):
        rospy.logdebug("Creating message for goal call")
        already_set = []
        if isinstance(inputs, tuple):
            arg_counter = 0
            object_counter = 0
            while (arg_counter < len(inputs) and object_counter < len(sample.__slots__)):
                cur_arg = inputs[arg_counter]
                cur_slot = sample.__slots__[object_counter]
                real_slot = getattr(sample, cur_slot)
                rospy.logdebug(
                    "cur_arg: " + str(cur_arg) + " cur_slot_name: " + str(cur_slot) + " real slot content: " + str(
                        real_slot))
                if hasattr(real_slot, '_type'):
                    rospy.logdebug("We found an object with name " + str(cur_slot) + ", creating it recursively")
                    already_set, arg_counter = self.create_object_instance(already_set, real_slot, cur_slot,
                                                                           arg_counter, inputs, sample)
                    object_counter += 1
                else:
                    already_set.append(cur_slot)
                    # set the attribute in the request
                    setattr(sample, cur_slot, cur_arg)
                    arg_counter += 1
                    object_counter += 1

        return sample


    def create_object_instance(self, already_set, object, name, counter, inputs, sample):
        rospy.loginfo("Create Object Instance Notify")
        object_counter = 0
        while (object_counter < len(object.__slots__) and counter < len(inputs)):
            cur_arg = inputs[counter]
            cur_slot = object.__slots__[object_counter]
            real_slot = getattr(object, cur_slot)
            rospy.loginfo(
                "cur_arg: " + str(cur_arg) + " cur_slot_name: " + str(cur_slot) + " real slot content: " + str(
                    real_slot))
            if hasattr(real_slot, '_type'):
                rospy.logdebug("Recursive Object found in request/response of service call")
                already_set, counter = self.create_object_instance(already_set, real_slot, cur_slot, counter, inputs,
                                                                   sample)
                object_counter += 1
            else:
                already_set.append(cur_slot)
                setattr(object, cur_slot, cur_arg)
                object_counter += 1
                counter += 1
                # sets the object as an attribute in the request were trying to build
        setattr(sample, name, object)
        return already_set, counter


    def recursive_delete_nodes(self, node):
        # close ros proxy service
        self.proxy.close()

        for child in node.get_children():
            self.recursive_delete_nodes(child)

            if child in self._nodes:
                del self._nodes[child]

            self.server.server.delete_nodes([child])

        self.server.server.delete_nodes([self.method])
        ros_server.own_rosnode_cleanup()


def ros_msg_to_flat_values(msg):
    array = []
    for slot_name, slot_type in zip(msg.__slots__, msg._slot_types):
        rospy.logdebug("converting slot name: '%s' with type: '%s'", slot_name, slot_type)
        slot_value = getattr(msg, slot_name)
        if hasattr(slot_value, '_type'):
            array_to_merge = ros_msg_to_flat_values(slot_value)
            array.extend(array_to_merge)
        else:
            array.append(slot_value)

    return array


def extract_array_info(type_str):
    array_size = None
    if '[' in type_str and type_str[-1] == ']':
        type_str, array_size_str = type_str.split('[', 1)
        array_size_str = array_size_str[:-1]
        if len(array_size_str) > 0:
            array_size = int(array_size_str)
        else:
            array_size = 0

    return type_str, array_size
