"""
bgpNgpf.py:

   Tested with two back-2-back Ixia ports...

   - Connect to the API server
   - Configure license server IP
   - Assign ports:
        - If variable forceTakePortOwnership is True, take over the ports if they're owned by another user.
        - If variable forceTakePortOwnership if False, abort test.
   - Configure two Topology Groups: IPv4/BGP
   - Configure Network Group for each topology for route advertising
   - Configure a Traffic Item
   - Start all protocols
   - Verify all protocols
   - Start traffic
   - Get Traffic Item
   - Get Flow Statistics stats

Supports IxNetwork API servers:
   - Windows, Windows Connection Mgr and Linux

Requirements:
   - Minimum IxNetwork 8.50
   - Python 2.7 and 3+
   - pip install requests
   - pip install ixnetwork_restpy (minimum version 1.0.51)

RestPy Doc:
    https://www.openixia.github.io/ixnetwork_restpy

Usage:
   - Enter: python <script>
"""

import sys, os, time, traceback

# Import the RestPy module
from ixnetwork_restpy import SessionAssistant

# For linux and connection_manager only. Set to True to leave the session alive for debugging.
debugMode = False

try:
    # LogLevel: none, info, warning, request, request_response, all
    session = SessionAssistant(IpAddress='192.168.70.12', RestPort=None, UserName='admin', Password='admin', 
                               SessionName=None, SessionId=None, ApiKey=None,
                               ClearConfig=True, LogLevel='info', LogFilename='restpy.log')

    ixNetwork = session.Ixnetwork

    ixNetwork.info('Assign ports')
    portMap = session.PortMapAssistant()
    vport1 = portMap.Map(IpAddress='192.168.70.128', CardId=1, PortId=1, Name='Port_1')
    vport2 = portMap.Map(IpAddress='192.168.70.128', CardId=2, PortId=1, Name='Port_2')

    portMap.Connect(ForceOwnership=True)

    ixNetwork.info('Creating Topology Group 1')
    topology1 = ixNetwork.Topology.add(Name='Topo1', Ports=vport1)

    ixNetwork.info('Creating Device Group 1')
    deviceGroup1 = topology1.DeviceGroup.add(Name='DG1', Multiplier='1')

    ixNetwork.info('Creating Ethernet stack 1')
    ethernet1 = deviceGroup1.Ethernet.add(Name='Eth1')
    ethernet1.Mac.Increment(start_value='00:01:01:01:00:01', step_value='00:00:00:00:00:01')

    ixNetwork.info('Enabling Vlan on Topology 1')
    ethernet1.EnableVlans.Single(True)

    ixNetwork.info('Configuring vlanID')
    vlanObj = ethernet1.Vlan.find()[0].VlanId.Increment(start_value=103, step_value=0)

    ixNetwork.info('Configuring IPv4')
    ipv4 = ethernet1.Ipv4.add(Name='Ipv4')
    ipv4.Address.Increment(start_value='1.1.1.1', step_value='0.0.0.1')
    ipv4.GatewayIp.Increment(start_value='1.1.1.2', step_value='0.0.0.0')

    ixNetwork.info('Configuring BgpIpv4Peer 1')
    bgp1 = ipv4.BgpIpv4Peer.add(Name='Bgp1')
    bgp1.DutIp.Increment(start_value='1.1.1.2', step_value='0.0.0.0')
    bgp1.Type.Single('internal')
    bgp1.LocalAs2Bytes.Increment(start_value=101, step_value=0)

    ixNetwork.info('Configuring Network Group 1')
    networkGroup1 = deviceGroup1.NetworkGroup.add(Name='BGP-Routes1', Multiplier='100')
    ipv4PrefixPool = networkGroup1.Ipv4PrefixPools.add(NumberOfAddresses='1')
    ipv4PrefixPool.NetworkAddress.Increment(start_value='10.10.0.1', step_value='0.0.0.1')
    ipv4PrefixPool.PrefixLength.Single(32)

    ixNetwork.info('Creating Topology Group 2')
    topology2 = ixNetwork.Topology.add(Name='Topo2', Ports=vport2)

    ixNetwork.info('Creating Device Group 2')
    deviceGroup2 = topology2.DeviceGroup.add(Name='DG2', Multiplier='1')

    ixNetwork.info('Creating Ethernet 2')
    ethernet2 = deviceGroup2.Ethernet.add(Name='Eth2')
    ethernet2.Mac.Increment(start_value='00:01:01:02:00:01', step_value='00:00:00:00:00:01')

    ixNetwork.info('Enabling Vlan on Topology 2')
    ethernet2.EnableVlans.Single(True)

    ixNetwork.info('Configuring vlanID')
    vlanObj = ethernet2.Vlan.find()[0].VlanId.Increment(start_value=103, step_value=0)

    ixNetwork.info('Configuring IPv4 2')
    ipv4 = ethernet2.Ipv4.add(Name='Ipv4-2')
    ipv4.Address.Increment(start_value='1.1.1.2', step_value='0.0.0.1')
    ipv4.GatewayIp.Increment(start_value='1.1.1.1', step_value='0.0.0.0')

    ixNetwork.info('Configuring BgpIpv4Peer 2')
    bgp2 = ipv4.BgpIpv4Peer.add(Name='Bgp2')
    bgp2.DutIp.Increment(start_value='1.1.1.1', step_value='0.0.0.0')
    bgp2.Type.Single('internal')
    bgp2.LocalAs2Bytes.Increment(start_value=101, step_value=0)

    ixNetwork.info('Configuring Network Group 2')
    networkGroup2 = deviceGroup2.NetworkGroup.add(Name='BGP-Routes2', Multiplier='100')
    ipv4PrefixPool = networkGroup2.Ipv4PrefixPools.add(NumberOfAddresses='1')
    ipv4PrefixPool.NetworkAddress.Increment(start_value='20.20.0.1', step_value='0.0.0.1')
    ipv4PrefixPool.PrefixLength.Single(32)

    ixNetwork.info('Starting NGPF protocols')
    ixNetwork.StartAllProtocols(Arg1='sync')

    ixNetwork.info('Verify protocol sessions\n')
    protocolSummary = session.StatViewAssistant('Protocols Summary')
    protocolSummary.CheckCondition('Sessions Not Started', protocolSummary.EQUAL, 0)
    protocolSummary.CheckCondition('Sessions Down', protocolSummary.EQUAL, 0)

    ixNetwork.info('Create Traffic Item')
    trafficItem = ixNetwork.Traffic.TrafficItem.add(Name='BGP Traffic', BiDirectional=False, TrafficType='ipv4')

    ixNetwork.info('Add source/dest endpoints')
    trafficItem.EndpointSet.add(Sources=topology1, Destinations=topology2)

    # Note: A Traffic Item could have multiple EndpointSets (Flow groups).
    #       Therefore, ConfigElement is a list.
    ixNetwork.info('Configuring config elements')
    configElement = trafficItem.ConfigElement.find()[0]
    configElement.FrameRate.update(Type='percentLineRate', Rate=50)
    configElement.TransmissionControl.update(Type='fixedFrameCount', FrameCount=10000)
    configElement.FrameRateDistribution.PortDistribution = 'splitRateEvenly'
    configElement.FrameSize.FixedSize = 128
    trafficItem.Tracking.find()[0].TrackBy = ['flowGroup0']

    trafficItem.Generate()

    ixNetwork.info('Apply config')
    ixNetwork.Traffic.Apply()

    ixNetwork.info('Starting traffic')
    ixNetwork.Traffic.StartStatelessTrafficBlocking()

    flowStatistics = session.StatViewAssistant('Flow Statistics')

    ixNetwork.info('{}\n'.format(flowStatistics))

    for rowNumber,flowStat in enumerate(flowStatistics.Rows):
        ixNetwork.info('\n\nSTATS: {}\n\n'.format(flowStat))
        ixNetwork.info('\nRow:{}  TxPort:{}  RxPort:{}  TxFrames:{}  RxFrames:{}\n'.format(
            rowNumber, flowStat['Tx Port'], flowStat['Rx Port'],
            flowStat['Tx Frames'], flowStat['Rx Frames']))

    if debugMode == False:
        # For linux and connection_manager only
        session.Session.remove()

except Exception as errMsg:
    print('\n%s' % traceback.format_exc(None, errMsg))
    if debugMode == False and 'session' in locals():
        session.Session.remove()





