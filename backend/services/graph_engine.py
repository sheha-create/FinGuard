import networkx as nx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class GraphEngine:
    def __init__(self, window_hours: int = 168, max_hops: int = 5):
        self.graph = nx.DiGraph()
        self.window_hours = window_hours
        self.max_hops = max_hops
        self.tx_metadata = {}

    def add_transaction(self, tx_id: str, sender: str, receiver: str, 
                       amount: float, timestamp: str, risk_score: float = 0.0,
                       skip_cleanup: bool = False):
        self.graph.add_edge(sender, receiver, 
                           tx_id=tx_id,
                           amount=amount,
                           timestamp=timestamp,
                           risk_score=risk_score)
        
        self.tx_metadata[tx_id] = {
            'sender': sender,
            'receiver': receiver,
            'amount': amount,
            'timestamp': timestamp,
            'risk_score': risk_score
        }
        
        if not skip_cleanup:
            self._cleanup_old_edges()

    def _cleanup_old_edges(self):
        cutoff = datetime.utcnow() - timedelta(hours=self.window_hours)
        edges_to_remove = []
        
        for u, v, data in self.graph.edges(data=True):
            tx_time = datetime.fromisoformat(data['timestamp'])
            if tx_time < cutoff:
                edges_to_remove.append((u, v))
        
        for edge in edges_to_remove:
            self.graph.remove_edge(*edge)

    def detect_cycles(self, start_node: str) -> List[Dict[str, Any]]:
        cycles = []
        
        if start_node not in self.graph:
            return cycles
        
        try:
            all_cycles = list(nx.simple_cycles(self.graph))
            
            for cycle in all_cycles:
                if start_node in cycle and len(cycle) <= self.max_hops + 1:
                    cycle_edges = []
                    total_amount = 0
                    min_risk = float('inf')
                    
                    for i in range(len(cycle)):
                        sender = cycle[i]
                        receiver = cycle[(i + 1) % len(cycle)]
                        
                        if self.graph.has_edge(sender, receiver):
                            edge_data = self.graph[sender][receiver]
                            cycle_edges.append({
                                'sender': sender,
                                'receiver': receiver,
                                'tx_id': edge_data.get('tx_id'),
                                'amount': edge_data.get('amount', 0),
                                'risk_score': edge_data.get('risk_score', 0)
                            })
                            total_amount += edge_data.get('amount', 0)
                            min_risk = min(min_risk, edge_data.get('risk_score', 0))
                    
                    if cycle_edges:
                        avg_risk = sum(e['risk_score'] for e in cycle_edges) / len(cycle_edges)
                        cycles.append({
                            'type': 'loop',
                            'accounts': cycle,
                            'edges': cycle_edges,
                            'length': len(cycle),
                            'total_amount': total_amount,
                            'avg_risk_score': avg_risk,
                            'min_risk_score': min_risk
                        })
        
        except nx.NetworkXError as e:
            logger.error(f"Error detecting cycles: {e}")
        
        return cycles

    def detect_fan_out(self, node: str, threshold: int = 5, window_hours: int = 24) -> Optional[Dict[str, Any]]:
        if node not in self.graph:
            return None
        
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        
        outgoing_edges = []
        for u, v, data in self.graph.out_edges(node, data=True):
            tx_time = datetime.fromisoformat(data['timestamp'])
            if tx_time >= cutoff:
                outgoing_edges.append({
                    'receiver': v,
                    'tx_id': data.get('tx_id'),
                    'amount': data.get('amount', 0),
                    'timestamp': data['timestamp'],
                    'risk_score': data.get('risk_score', 0)
                })
        
        if len(outgoing_edges) >= threshold:
            unique_receivers = len(set(e['receiver'] for e in outgoing_edges))
            total_amount = sum(e['amount'] for e in outgoing_edges)
            avg_risk = sum(e['risk_score'] for e in outgoing_edges) / len(outgoing_edges)
            
            return {
                'type': 'fan_out',
                'source_account': node,
                'edges': outgoing_edges,
                'receiver_count': unique_receivers,
                'transaction_count': len(outgoing_edges),
                'total_amount': total_amount,
                'avg_risk_score': avg_risk,
                'window_hours': window_hours
            }
        
        return None

    def detect_fan_in(self, node: str, threshold: int = 5, window_hours: int = 24) -> Optional[Dict[str, Any]]:
        if node not in self.graph:
            return None
        
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        
        incoming_edges = []
        for u, v, data in self.graph.in_edges(node, data=True):
            tx_time = datetime.fromisoformat(data['timestamp'])
            if tx_time >= cutoff:
                incoming_edges.append({
                    'sender': u,
                    'tx_id': data.get('tx_id'),
                    'amount': data.get('amount', 0),
                    'timestamp': data['timestamp'],
                    'risk_score': data.get('risk_score', 0)
                })
        
        if len(incoming_edges) >= threshold:
            unique_senders = len(set(e['sender'] for e in incoming_edges))
            total_amount = sum(e['amount'] for e in incoming_edges)
            avg_risk = sum(e['risk_score'] for e in incoming_edges) / len(incoming_edges)
            
            return {
                'type': 'fan_in',
                'target_account': node,
                'edges': incoming_edges,
                'sender_count': unique_senders,
                'transaction_count': len(incoming_edges),
                'total_amount': total_amount,
                'avg_risk_score': avg_risk,
                'window_hours': window_hours
            }
        
        return None

    def compute_graph_score(self, sender: str, receiver: str) -> float:
        score = 0.0
        
        cycles = self.detect_cycles(sender)
        if cycles:
            max_cycle_risk = max(c['avg_risk_score'] for c in cycles)
            score = max(score, min(max_cycle_risk * 1.2, 1.0))
        
        fan_out = self.detect_fan_out(sender, threshold=3, window_hours=1)
        if fan_out:
            fan_out_score = min(fan_out['receiver_count'] / 10, 1.0) * 0.8
            score = max(score, fan_out_score)
        
        fan_in = self.detect_fan_in(receiver, threshold=3, window_hours=1)
        if fan_in:
            fan_in_score = min(fan_in['sender_count'] / 10, 1.0) * 0.8
            score = max(score, fan_in_score)
        
        if self.graph.has_edge(sender, receiver):
            edge_data = self.graph[sender][receiver]
            amount = edge_data.get('amount', 0)
            if amount > 9000:
                structuring_score = min((amount - 9000) / 1000 * 0.5, 0.5)
                score = max(score, structuring_score)
        
        return float(min(score, 1.0))

    def detect_patterns(self, sender: str, receiver: str) -> List[Dict[str, Any]]:
        patterns = []
        
        cycles = self.detect_cycles(sender)
        patterns.extend(cycles)
        
        fan_out = self.detect_fan_out(sender, threshold=3, window_hours=1)
        if fan_out:
            patterns.append(fan_out)
        
        fan_in = self.detect_fan_in(receiver, threshold=3, window_hours=1)
        if fan_in:
            patterns.append(fan_in)
        
        return patterns

    def get_account_subgraph(self, account_id: str, hops: int = 2) -> Dict[str, Any]:
        if account_id not in self.graph:
            return {"nodes": [], "edges": []}
        
        nodes = set()
        nodes.add(account_id)
        
        current_level = {account_id}
        for _ in range(hops):
            next_level = set()
            for node in current_level:
                for neighbor in self.graph.successors(node):
                    if neighbor not in nodes:
                        next_level.add(neighbor)
                        nodes.add(neighbor)
                for neighbor in self.graph.predecessors(node):
                    if neighbor not in nodes:
                        next_level.add(neighbor)
                        nodes.add(neighbor)
            current_level = next_level
        
        subgraph = self.graph.subgraph(nodes)
        
        graph_data = {
            "nodes": [],
            "edges": []
        }
        
        for node in subgraph.nodes():
            out_degree = subgraph.out_degree(node)
            in_degree = subgraph.in_degree(node)
            graph_data["nodes"].append({
                "id": node,
                "label": node,
                "out_degree": out_degree,
                "in_degree": in_degree,
                "is_center": node == account_id
            })
        
        for u, v, data in subgraph.edges(data=True):
            graph_data["edges"].append({
                "source": u,
                "target": v,
                "tx_id": data.get('tx_id'),
                "amount": data.get('amount', 0),
                "risk_score": data.get('risk_score', 0),
                "timestamp": data.get('timestamp')
            })
        
        return graph_data

    def get_graph_stats(self) -> Dict[str, Any]:
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "window_hours": self.window_hours,
            "max_hops": self.max_hops
        }


graph_engine = GraphEngine()
