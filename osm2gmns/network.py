from .readfile import *
from .simplification import *
from .complex_intersection import *
from .wayfilters import *
import re


def parseNodes(network, nodes, strict_mode):
    for osm_node in nodes:
        node = Node()
        node.osm_node_id = osm_node.attrib['id']
        node.node_no = network.created_nodes
        node.x_coord = float(osm_node.attrib['lon'])
        node.y_coord = float(osm_node.attrib['lat'])

        if strict_mode:
            if not ((network.minlon <= node.x_coord <= network.maxlon) and (network.minlat <= node.y_coord <= network.maxlat)):
                node.in_region = False

        for info in osm_node:
            if info.tag == 'tag':
                if info.attrib['k'] == 'highway':
                    node.osm_highway = info.attrib['v']

        if 'signal' in node.osm_highway: node.ctrl_type = 1         # todo: check signalized tag

        network.node_set.add(node)
        network.osm_node_id_to_node_dict[node.osm_node_id] = node
        network.created_nodes += 1


def newLinkFromWay(link_no, way, direction, ref_node_list):
    link = Link()
    link.osm_way_id = way.osm_way_id
    link.link_no = link_no
    link.name = way.name
    link.link_type_name = way.link_type_name
    link.link_type = way.link_type
    link.free_speed = way.maxspeed
    link.allowed_uses = way.allowed_uses

    if way.oneway:
        link.lanes_list = [way.lanes]
    else:
        if direction == 1:
            if way.forward_lanes is not None:
                link.lanes_list = [way.forward_lanes]
            elif way.lanes is not None:
                link.lanes_list = [math.ceil(way.lanes / 2)]
            else:
                link.lanes_list = [way.lanes]
        else:
            if way.backward_lanes is not None:
                link.lanes_list = [way.backward_lanes]
            elif way.lanes is not None:
                link.lanes_list = [math.ceil(way.lanes / 2)]
            else:
                link.lanes_list = [way.lanes]

    link.lanes = link.lanes_list[0]
    link.from_node = ref_node_list[0]
    link.to_node = ref_node_list[-1]
    link.from_node.outgoing_link_list.append(link)
    link.to_node.incoming_link_list.append(link)
    for ref_node in ref_node_list: link.geometry_point_list.append((ref_node.x_coord,ref_node.y_coord))
    link.getGeometryStr()
    link.calculateLength()

    return link


def getCoordOnBoundary(node_in,node_outside,network):
    if node_in.x_coord == node_outside.x_coord:
        x_coord = node_in.x_coord
        if node_outside.y_coord > network.maxlat:
            y_coord = network.maxlat
        else:
            y_coord = network.minlat
        return x_coord, y_coord

    if node_outside.x_coord > network.maxlon:
        x_coord = network.maxlon
        y_coord = (node_outside.y_coord - node_in.y_coord)/(node_outside.x_coord - node_in.x_coord) * (x_coord-node_in.x_coord) + node_in.y_coord
        if network.minlat <= y_coord <= network.maxlat:
            return x_coord, y_coord

    if node_outside.x_coord < network.minlon:
        x_coord = network.minlon
        y_coord = (node_outside.y_coord - node_in.y_coord)/(node_outside.x_coord - node_in.x_coord) * (x_coord-node_in.x_coord) + node_in.y_coord
        if network.minlat <= y_coord <= network.maxlat:
            return x_coord, y_coord

    if node_outside.y_coord > network.maxlat:
        y_coord = network.maxlat
        x_coord = (node_outside.x_coord - node_in.x_coord) / (node_outside.y_coord - node_in.y_coord) * (y_coord - node_in.y_coord) + node_in.x_coord
        if network.minlon <= x_coord <= network.maxlon:
            return x_coord, y_coord

    if node_outside.y_coord < network.minlat:
        y_coord = network.minlat
        x_coord = (node_outside.x_coord - node_in.x_coord) / (node_outside.y_coord - node_in.y_coord) * (y_coord - node_in.y_coord) + node_in.x_coord
        if network.minlon <= x_coord <= network.maxlon:
            return x_coord, y_coord

    raise Exception('cannot build a node on the boundary')



def createNodeOnBoundary(node_in,node_outside,network):
    node = Node()
    node.node_no = network.created_nodes
    node.x_coord, node.y_coord = getCoordOnBoundary(node_in,node_outside,network)
    node.is_crossing = True

    network.node_set.add(node)
    network.osm_node_id_to_node_dict[node.osm_node_id] = node
    network.created_nodes += 1

    return node


def getSegmentNodeList(way, segment_no, network):
    m_segment_node_list = way.segment_node_list[segment_no]
    if way.is_reversed: m_segment_node_list = list(reversed(m_segment_node_list))
    number_of_nodes = len(m_segment_node_list)

    m_segment_node_list_group = []

    if m_segment_node_list[0].in_region:
        idx_first_outside = -1
        for idx, node in enumerate(m_segment_node_list):
            if not node.in_region:
                idx_first_outside = idx
                break

        if idx_first_outside == -1:
            m_segment_node_list_group.append(m_segment_node_list)
            return m_segment_node_list_group
        else:
            new_node = createNodeOnBoundary(m_segment_node_list[idx_first_outside-1],m_segment_node_list[idx_first_outside], network)
            m_segment_node_list_group.append(m_segment_node_list[:idx_first_outside] + [new_node])

    if m_segment_node_list[-1].in_region:
        idx_last_outside = -1
        for idx in range(number_of_nodes-2,-1,-1):
            if not m_segment_node_list[idx].in_region:
                idx_last_outside = idx
                break
        new_node = createNodeOnBoundary(m_segment_node_list[idx_last_outside+1],m_segment_node_list[idx_last_outside], network)
        m_segment_node_list_group.append([new_node] + m_segment_node_list[idx_last_outside+1:])

    return m_segment_node_list_group


def createLinks(network, way_list):
    for way in way_list:
        if way.is_cycle:
            crossing_in_cycle = False
            for node in way.ref_node_list[1:-1]:
                if node.is_crossing:
                    crossing_in_cycle = True
                    break
            if not crossing_in_cycle: continue

        way.getNodeListForSegments()
        for segment_no in range(way.number_of_segments):

            m_segment_node_list_group = getSegmentNodeList(way, segment_no, network)
            for m_segment_node_list in m_segment_node_list_group:
                link = newLinkFromWay(network.created_links, way, 1, m_segment_node_list)
                network.link_set.add(link)
                network.created_links += 1
                if not way.oneway:
                    linkb = newLinkFromWay(network.created_links, way, -1, list(reversed(m_segment_node_list)))
                    network.link_set.add(linkb)
                    network.created_links += 1


def parseWays(network, ways, network_type):
    way_list = []
    network_type_set = set(network_type)

    for osm_way in ways:
        way = Way()
        way.osm_way_id = osm_way.attrib['id']

        for info in osm_way:
            if info.tag == 'nd':
                ref_node_id = info.attrib['ref']
                try:
                    way.ref_node_list.append(network.osm_node_id_to_node_dict[ref_node_id])
                except KeyError:
                    print(f'  warning: ref node {ref_node_id} in way {way.osm_way_id} is not defined')
            elif info.tag == 'tag':
                if info.attrib['k'] == 'highway':
                    way.highway = info.attrib['v']
                elif info.attrib['k'] == 'lanes':
                    lanes = re.findall(r'\d+\.?\d*', info.attrib['v'])
                    if len(lanes) > 0:
                        way.lanes = int(float(lanes[0]))        # in case of decimals
                    else:
                        printlog(f'new lanes type detected at way {way.osm_way_id}, {info.attrib["v"]}','warning')
                elif info.attrib['k'] == 'lanes:forward':
                    way.forward_lanes = int(info.attrib['v'])
                elif info.attrib['k'] == 'lanes:backward':
                    way.backward_lanes = int(info.attrib['v'])
                elif info.attrib['k'] == 'name':
                    way.name = info.attrib['v']
                elif info.attrib['k'] == 'maxspeed':
                    speeds = re.findall(r'\d+\.?\d*', info.attrib['v'])
                    if len(speeds) > 0:
                        way.maxspeed = speeds[0]
                    else:
                        printlog(f'new maxspeed type detected at way {way.osm_way_id}, {info.attrib["v"]}','warning')
                elif info.attrib['k'] == 'oneway':
                    oneway_flag = info.attrib['v']
                    if oneway_flag == 'yes' or oneway_flag == '1':
                        way.oneway = True
                    elif oneway_flag == 'no' or oneway_flag == '0':
                        way.oneway = False
                    elif oneway_flag == '-1':
                        way.oneway = True
                        way.is_reversed = True
                    elif oneway_flag in ['reversible', 'alternating']:
                        # todo: reversible, alternating: https://wiki.openstreetmap.org/wiki/Tag:oneway%3Dreversible
                        way.oneway = False
                    else:
                        printlog(f'new maxspeed type detected at way {way.osm_way_id}, {info.attrib["v"]}','warning')
                elif info.attrib['k'] == 'area':
                    way.area = info.attrib['v']
                elif info.attrib['k'] == 'motor_vehicle':
                    way.motor_vehicle = info.attrib['v']
                elif info.attrib['k'] == 'motorcar':
                    way.motorcar = info.attrib['v']
                elif info.attrib['k'] == 'service':
                    way.service = info.attrib['v']
                elif info.attrib['k'] == 'foot':
                    way.foot = info.attrib['v']
                elif info.attrib['k'] == 'bicycle':
                    way.bicycle = info.attrib['v']

        if way.highway:
            try:
                way.link_type_name = osm_highway_type_dict[way.highway]
                way.link_type = link_type_no_dict[way.link_type_name]
            except KeyError:
                continue

            if len(way.ref_node_list) < 2: continue

            allowable_agent_type_list = getAllowableAgentType(way)
            way.allowable_agent_type_list = list(set(allowable_agent_type_list).intersection(network_type_set))
            if len(way.allowable_agent_type_list) == 0:
                continue
            way.allowed_uses = ';'.join(way.allowable_agent_type_list)

            if way.ref_node_list[0] is way.ref_node_list[-1]:
                way.is_cycle = True

            if way.oneway is None:
                way.oneway = default_oneway_flag_dict[way.link_type_name]

            if way.lanes is None:
                if network.default_lanes:
                    way.lanes = network.default_lanes[way.link_type_name]
            if way.maxspeed is None:
                if network.default_speed:
                    way.maxspeed = network.default_speed[way.link_type_name]

            way_list.append(way)


    used_node_set = set()
    for way in way_list:
        way.ref_node_list[0].is_crossing = True
        way.ref_node_list[-1].is_crossing = True
        for node in way.ref_node_list[1:-1]:
            if node in used_node_set:
                node.is_crossing = True
            else:
                used_node_set.add(node)

    createLinks(network, way_list)


def parseOSM(network, nodes, ways, strict_mode, network_type):
    parseNodes(network, nodes, strict_mode)
    parseWays(network, ways, network_type)


def removeUseless(network):
    remove_node_set = set()
    for node in network.node_set:
        if not (node.is_crossing and node.in_region):
            remove_node_set.add(node)
    for node in remove_node_set:
        network.node_set.remove(node)


def removeIsolated(network):
    # node_list = sorted(network.node_set,key=network.node.osm_node_id)

    node_list = list(network.node_set)
    node_to_idx_dict = {}
    for idx, node in enumerate(node_list): node_to_idx_dict[node] = idx
    number_of_nodes = len(node_list)
    node_group_id_list = [-1] * number_of_nodes

    group_id = 0
    start_idx = 0

    while True:
        unprocessed_node_list = [node_list[start_idx]]
        node_group_id_list[start_idx] = group_id
        while unprocessed_node_list:
            node = unprocessed_node_list.pop()
            for ob_link in node.outgoing_link_list:
                ob_node = ob_link.to_node
                if node_group_id_list[node_to_idx_dict[ob_node]] == -1:
                    node_group_id_list[node_to_idx_dict[ob_node]] = group_id
                    unprocessed_node_list.append(ob_node)

            for ib_link in node.incoming_link_list:
                ib_node = ib_link.from_node
                if node_group_id_list[node_to_idx_dict[ib_node]] == -1:
                    node_group_id_list[node_to_idx_dict[ib_node]] = group_id
                    unprocessed_node_list.append(ib_node)

        unreachable_node_exits = False
        for idx in range(start_idx+1,number_of_nodes):
            if node_group_id_list[idx] == -1:
                unreachable_node_exits = True
                break

        if unreachable_node_exits:
            start_idx = idx
            group_id += 1
        else:
            break

    group_id_set = set(node_group_id_list)
    max_group_id = 0
    max_group_size = 0
    for group_id in group_id_set:
        group_size = node_group_id_list.count(group_id)
        if group_size > max_group_size:
            max_group_size = group_size
            max_group_id = group_id

    removal_link_set = set()
    for idx, node in enumerate(node_list):
        if node_group_id_list[idx] != max_group_id:
            network.node_set.remove(node)
            for ob_link in node.outgoing_link_list: removal_link_set.add(ob_link)
            for ib_link in node.incoming_link_list: removal_link_set.add(ib_link)
    for link in removal_link_set:
        network.link_set.remove(link)


def assignNewID(network):
    number_of_nodes = 0
    number_of_links = 0

    # ensure node_id and link_id keep unchanged between different runs
    node_list = sorted(network.node_set, key=lambda x: x.node_no)
    link_list = sorted(network.link_set, key=lambda x: x.link_no)

    for node in node_list:
        node.node_id = number_of_nodes
        network.node_id_to_node_dict[node.node_id] = node
        number_of_nodes += 1

    for link in link_list:
        link.link_id = number_of_links
        number_of_links += 1


def getValidNetworkType(network_type):
    if isinstance(network_type,str):
        network_type_temp = (network_type,)
    else:
        network_type_temp = network_type

    network_type_valid = []
    network_type_all = list(filters.keys())
    for net_type in network_type_temp:
        if net_type not in network_type_all:
            print(f'network type \'{net_type}\' does not belong to {network_type_all}, it will be skipped')
        else:
            network_type_valid.append(net_type)
    return network_type_valid


def getNetFromOSMFile(osm_filename='map.osm', network_type=('auto',), strict_mode=True, remove_isolated=True, simplify=True,
                      int_buffer=default_int_buffer, bbox=None, default_lanes=False, default_speed=False):
    """
    :param osm_filename:
    :param network_type:
    :param strict_mode:
    :param remove_isolated:
    :param simplify:
    :param int_buffer:
    :param bbox: (minlat, minlon, maxlat, maxlon)
    :param default_lanes: True; False; Dict
    :param default_speed: True; False; Dict
    :return: a network instance
    """
    # build network
    network = Network()

    if default_lanes:
        if isinstance(default_lanes,bool):
            network.default_lanes = default_lanes_dict
        elif isinstance(default_lanes,dict):
            network.default_lanes = default_lanes
            for link_type_name, lanes in default_lanes_dict.items():
                if link_type_name not in default_lanes.keys():
                    network.default_lanes[link_type_name] = lanes
        else:
            print('unsupported type for argument default_lanes, has set it to default value: False')
    if default_speed:
        if isinstance(default_speed,bool):
            network.default_speed = default_speed_dict
        elif isinstance(default_speed,dict):
            network.default_speed = default_speed
            for link_type_name, speed in default_speed_dict.items():
                if link_type_name not in default_speed.keys():
                    network.default_speed[link_type_name] = speed
        else:
            print('unsupported type for argument default_lanes, has set it to default value: False')

    bounds, nodes, ways = readXMLFile(osm_filename)

    if bbox is None:
        network.minlat, network.minlon, network.maxlat, network.maxlon = bounds['minlat'], bounds['minlon'], bounds['maxlat'], bounds['maxlon']
    else:
        network.minlat, network.minlon, network.maxlat, network.maxlon = bbox

    network_type_valid = getValidNetworkType(network_type)
    parseOSM(network, nodes, ways, strict_mode, network_type_valid)
    del nodes, ways

    removeUseless(network)

    # remove isolated nodes and links
    if remove_isolated:
        removeIsolated(network)

    # merge adjacent links at two-degree nodes
    if simplify:
        simplifyNetwork(network)

    # identify complex intersections which contains multiple nodes
    identifyComplexIntersections(network,int_buffer)

    # assign new ids starting from 0 to nodes and links
    assignNewID(network)

    return network


def getNetFromCSV(folder=''):
    node_data, link_data = readCSVFile(folder)
    network = Network()

    for i in range(len(node_data)):
        node = Node()
        node.node_id = node_data.loc[i, 'node_id']
        osm_node_id = node_data.loc[i, 'osm_node_id']
        if osm_node_id == osm_node_id: node.osm_node_id = osm_node_id
        osm_highway = node_data.loc[i, 'osm_highway']
        if osm_highway == osm_highway: node.osm_highway = osm_highway
        node.x_coord = node_data.loc[i, 'x_coord']
        node.y_coord = node_data.loc[i, 'y_coord']
        main_node_id = node_data.loc[i, 'main_node_id']
        if main_node_id == main_node_id: node.main_node_id = int(main_node_id)
        node.ctrl_type = node_data.loc[i, 'ctrl_type']
        network.node_set.add(node)

        network.node_id_to_node_dict[node.node_id] = node

    for i in range(len(link_data)):
        link = Link()
        name = link_data.loc[i, 'name']
        if name == name: link.name = name
        link.link_id = link_data.loc[i, 'link_id']
        link.osm_way_id = link_data.loc[i, 'osm_way_id']
        link.from_node = network.node_id_to_node_dict[link_data.loc[i, 'from_node_id']]
        link.to_node = network.node_id_to_node_dict[link_data.loc[i, 'to_node_id']]
        link.length = link_data.loc[i, 'length']
        lanes = link_data.loc[i, 'lanes']
        if lanes == lanes: link.lanes = lanes
        free_speed = link_data.loc[i, 'free_speed']
        if free_speed == free_speed: link.free_speed = free_speed
        link.link_type_name = link_data.loc[i, 'link_type_name']
        link.link_type = link_data.loc[i, 'link_type']
        link.geometry_str = link_data.loc[i, 'geometry']

        network.link_set.add(link)

        link.from_node.outgoing_link_list.append(link)
        link.to_node.incoming_link_list.append(link)

    return network


def generateNodeActivityInfo(network):
    node_adjacent_link_type_count_dict = {}

    for link in network.link_set:
        from_node = link.from_node
        if from_node not in node_adjacent_link_type_count_dict.keys():
            node_adjacent_link_type_count_dict[from_node] = {}
        adjacent_link_type_count_dict = node_adjacent_link_type_count_dict[from_node]

        if link.link_type_name in adjacent_link_type_count_dict.keys():
            adjacent_link_type_count_dict[link.link_type_name] += 1
        else:
            adjacent_link_type_count_dict[link.link_type_name] = 1

        to_node = link.to_node
        if to_node not in node_adjacent_link_type_count_dict.keys():
            node_adjacent_link_type_count_dict[to_node] = {}
        adjacent_link_type_count_dict = node_adjacent_link_type_count_dict[to_node]

        if link.link_type_name in adjacent_link_type_count_dict.keys():
            adjacent_link_type_count_dict[link.link_type_name] += 1
        else:
            adjacent_link_type_count_dict[link.link_type_name] = 1

    for node in network.node_set:
        adjacent_link_type_count_dict = node_adjacent_link_type_count_dict[node]
        max_count_type = ''
        max_count = 0
        for link_type_name, count in adjacent_link_type_count_dict.items():
            if count > max_count:
                max_count = count
                max_count_type = link_type_name
        node.activity_type = max_count_type

    for node in network.node_set:
        if (len(node.incoming_link_list) == 0) or (len(node.outgoing_link_list) == 0):
            node.is_boundary = True
            continue

        if (len(node.incoming_link_list) == 1) and (len(node.outgoing_link_list) == 1):
            ib_link = node.incoming_link_list[0]
            ob_link = node.outgoing_link_list[0]
            if ib_link.from_node is ob_link.to_node:
                node.is_boundary = True