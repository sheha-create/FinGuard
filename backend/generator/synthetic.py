import asyncio
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SyntheticGenerator:
    def __init__(self):
        self.accounts = []
        self.normal_accounts = []
        self.suspicious_accounts = []
        self._initialize_accounts()

    def _initialize_accounts(self):
        for i in range(100):
            account_id = f"acct_{uuid.uuid4().hex[:8]}"
            kyc_tier = random.choice(["low", "medium", "high"])
            account_type = random.choice(["personal", "business"])
            
            self.accounts.append({
                "id": account_id,
                "kyc_tier": kyc_tier,
                "account_type": account_type,
                "created_at": (datetime.utcnow() - timedelta(days=random.randint(30, 365))).isoformat()
            })
        
        self.normal_accounts = self.accounts[:80]
        self.suspicious_accounts = self.accounts[80:]

    def _generate_normal_transaction(self) -> Dict[str, Any]:
        sender = random.choice(self.normal_accounts)
        receiver = random.choice([a for a in self.normal_accounts if a['id'] != sender['id']])
        
        amount = round(random.lognormvariate(6, 1.5), 2)
        amount = max(10, min(amount, 50000))
        
        timestamp = datetime.utcnow() - timedelta(
            seconds=random.randint(0, 3600),
            minutes=random.randint(0, 60)
        )
        
        return {
            "id": f"tx_{uuid.uuid4().hex[:12]}",
            "sender": sender['id'],
            "receiver": receiver['id'],
            "amount": amount,
            "timestamp": timestamp.isoformat()
        }

    def _generate_loop_transaction(self, loop_accounts: List[Dict], index: int) -> Dict[str, Any]:
        sender = loop_accounts[index % len(loop_accounts)]
        receiver = loop_accounts[(index + 1) % len(loop_accounts)]
        
        amount = round(random.uniform(9000, 9999), 2)
        
        timestamp = datetime.utcnow() - timedelta(seconds=random.randint(0, 300))
        
        return {
            "id": f"tx_{uuid.uuid4().hex[:12]}",
            "sender": sender['id'],
            "receiver": receiver['id'],
            "amount": amount,
            "timestamp": timestamp.isoformat()
        }

    def _generate_fan_out_transaction(self, source_account: Dict, 
                                     target_accounts: List[Dict], index: int) -> Dict[str, Any]:
        receiver = target_accounts[index % len(target_accounts)]
        
        amount = round(random.uniform(8000, 9500), 2)
        
        timestamp = datetime.utcnow() - timedelta(seconds=random.randint(0, 600))
        
        return {
            "id": f"tx_{uuid.uuid4().hex[:12]}",
            "sender": source_account['id'],
            "receiver": receiver['id'],
            "amount": amount,
            "timestamp": timestamp.isoformat()
        }

    def _generate_fan_in_transaction(self, source_accounts: List[Dict], 
                                    target_account: Dict, index: int) -> Dict[str, Any]:
        sender = source_accounts[index % len(source_accounts)]
        
        amount = round(random.uniform(8500, 9800), 2)
        
        timestamp = datetime.utcnow() - timedelta(seconds=random.randint(0, 600))
        
        return {
            "id": f"tx_{uuid.uuid4().hex[:12]}",
            "sender": sender['id'],
            "receiver": target_account['id'],
            "amount": amount,
            "timestamp": timestamp.isoformat()
        }

    def generate_batch(self, count: int = 10, include_suspicious: bool = True) -> List[Dict[str, Any]]:
        transactions = []
        
        normal_count = count
        if include_suspicious and count >= 10:
            normal_count = count - 5
        
        for _ in range(normal_count):
            transactions.append(self._generate_normal_transaction())
        
        if include_suspicious and count >= 10:
            loop_accounts = random.sample(self.suspicious_accounts, 4)
            for i in range(3):
                transactions.append(self._generate_loop_transaction(loop_accounts, i))
            
            source = random.choice(self.suspicious_accounts)
            targets = random.sample([a for a in self.suspicious_accounts if a['id'] != source['id']], 4)
            for i in range(2):
                transactions.append(self._generate_fan_out_transaction(source, targets, i))
        
        random.shuffle(transactions)
        return transactions

    def generate_stream(self, rate_per_second: float = 1.0, 
                       duration_seconds: int = 60,
                       include_suspicious: bool = True):
        interval = 1.0 / rate_per_second
        end_time = datetime.utcnow() + timedelta(seconds=duration_seconds)
        
        while datetime.utcnow() < end_time:
            transactions = self.generate_batch(count=max(1, int(rate_per_second / 10)), 
                                             include_suspicious=include_suspicious)
            for tx in transactions:
                yield tx
            asyncio.sleep(interval)


generator = SyntheticGenerator()
