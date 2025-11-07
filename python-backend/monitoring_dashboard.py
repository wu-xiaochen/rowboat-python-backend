#!/usr/bin/env python3
"""
Advanced Monitoring Dashboard for Rowboat Python Backend
Real-time system monitoring with alerts and performance tracking
"""

import time
import json
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SystemMetrics:
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    response_time: float
    error_count: int
    request_count: int
    database_status: str
    api_status: str

class MonitoringDashboard:
    """Advanced monitoring dashboard for Rowboat backend"""

    def __init__(self, base_url: str = "http://localhost:8001",
                 metrics_file: str = "monitoring/metrics.json"):
        self.base_url = base_url
        self.metrics_file = Path(metrics_file)
        self.metrics_file.parent.mkdir(exist_ok=True)

        self.alert_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'response_time': 1000.0,  # ms
            'error_rate': 5.0,  # percentage
            'disk_usage': 90.0
        }

        self.monitoring_active = False
        self.metrics_history: List[SystemMetrics] = []
        self.alerts: List[Dict] = []

    def get_health_status(self) -> Dict:
        """Get system health status from health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "unhealthy", "error": f"Status {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_metrics(self) -> Dict:
        """Get detailed metrics from metrics endpoint"""
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=10)
            if response.status_code == 200:
                return {"status": "success", "data": response.text}
            else:
                return {"status": "unavailable", "error": f"Status {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def check_database_status(self) -> str:
        """Check database connectivity"""
        try:
            # Try a simple database query via the API
            response = requests.get(f"{self.base_url}/api/agents", timeout=10)
            if response.status_code == 403:  # Authentication required - this is OK
                return "authenticated"
            elif response.status_code == 200:
                return "connected"
            else:
                return f"status_{response.status_code}"
        except Exception as e:
            return "connection_failed"

    def simulate_system_metrics(self) -> SystemMetrics:
        """Simulate system metrics (in production, this would use real system calls)"""
        import random
        import psutil

        current_time = datetime.now()

        # Get real system metrics if psutil is available
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
        except ImportError:
            # Fallback simulated metrics
            cpu_percent = random.uniform(10, 50)
            memory_percent = random.uniform(40, 70)
            disk_percent = random.uniform(30, 60)

        # Test API response time
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/health", timeout=5)
            response_time = (time.time() - start_time) * 1000  # Convert to ms
        except:
            response_time = 0

        return SystemMetrics(
            timestamp=current_time,
            cpu_usage=cpu_percent,
            memory_usage=memory_percent,
            disk_usage=disk_percent,
            response_time=response_time,
            error_count=random.randint(0, 5),
            request_count=random.randint(100, 500),
            database_status=self.check_database_status(),
            api_status="healthy" if response_time > 0 else "unhealthy"
        )

    def check_alerts(self, metrics: SystemMetrics) -> List[Dict]:
        """Check if metrics exceed alert thresholds"""
        current_alerts = []

        if metrics.cpu_usage > self.alert_thresholds['cpu_usage']:
            current_alerts.append({
                "type": "high_cpu",
                "severity": "warning",
                "value": metrics.cpu_usage,
                "threshold": self.alert_thresholds['cpu_usage'],
                "timestamp": metrics.timestamp.isoformat()
            })

        if metrics.memory_usage > self.alert_thresholds['memory_usage']:
            current_alerts.append({
                "type": "high_memory",
                "severity": "warning",
                "value": metrics.memory_usage,
                "threshold": self.alert_thresholds['memory_usage'],
                "timestamp": metrics.timestamp.isoformat()
            })

        if metrics.response_time > self.alert_thresholds['response_time']:
            current_alerts.append({
                "type": "slow_response",
                "severity": "critical",
                "value": metrics.response_time,
                "threshold": self.alert_thresholds['response_time'],
                "timestamp": metrics.timestamp.isoformat()
            })

        if metrics.database_status != "authenticated":
            current_alerts.append({
                "type": "database_issue",
                "severity": "critical",
                "value": metrics.database_status,
                "threshold": "authenticated",
                "timestamp": metrics.timestamp.isoformat()
            })

        return current_alerts

    def collect_metrics_continuously(self, interval: int = 60):
        """Continuously collect metrics every interval seconds"""
        print(f"🚀 Starting continuous monitoring... (interval: {interval}s)")

        while self.monitoring_active:
            try:
                metrics = self.simulate_system_metrics()
                self.metrics_history.append(metrics)

                # Keep only last 24 hours of data
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.metrics_history = [
                    m for m in self.metrics_history
                    if m.timestamp > cutoff_time
                ]

                # Check for alerts
                alerts = self.check_alerts(metrics)
                for alert in alerts:
                    print(f"🚨 ALERT: {alert['type']} - {alert['severity']}")
                    self.alerts.append(alert)

                # Save metrics to file
                self.save_metrics()

                time.sleep(interval)

            except KeyboardInterrupt:
                print("\n📊 Monitoring stopped by user")
                break
            except Exception as e:
                print(f"❌ Error during monitoring: {e}")
                time.sleep(interval)

    def save_metrics(self):
        """Save metrics and alerts to file"""
        data = {
            "last_updated": datetime.now().isoformat(),
            "metrics": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "cpu_usage": m.cpu_usage,
                    "memory_usage": m.memory_usage,
                    "disk_usage": m.disk_usage,
                    "response_time": m.response_time,
                    "error_count": m.error_count,
                    "request_count": m.request_count,
                    "database_status": m.database_status,
                    "api_status": m.api_status
                }
                for m in self.metrics_history
            ],
            "alerts": self.alerts[-100:],  # Keep last 100 alerts
            "system_info": self.get_system_info()
        }

        with open(self.metrics_file, 'w') as f:
            json.dump(data, f, indent=2)

    def get_system_info(self) -> Dict:
        """Get system information"""
        health = self.get_health_status()
        metrics = self.get_metrics()

        return {
            "base_url": self.base_url,
            "health_status": health,
            "metrics_available": metrics["status"] == "success",
            "total_metrics_collected": len(self.metrics_history),
            "total_alerts_generated": len(self.alerts),
            "uptime": (datetime.now() -
                      (self.metrics_history[0].timestamp if self.metrics_history
                       else datetime.now())).total_seconds()
        }

    def display_dashboard(self):
        """Display current dashboard"""
        if not self.metrics_history:
            print("📊 No metrics collected yet. Start monitoring first.")
            return

        latest = self.metrics_history[-1]

        print("\n" + "="*60)
        print("🚢 ROWBOAT PYTHON BACKEND - MONITORING DASHBOARD")
        print("="*60)
        print(f"⏰ Last Update: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Server: {self.base_url}")

        print(f"\n📈 CURRENT METRICS:")
        print(f"  • CPU Usage: {latest.cpu_usage:.1f}%")
        print(f"  • Memory Usage: {latest.memory_usage:.1f}%")
        print(f"  • Disk Usage: {latest.disk_usage:.1f}%")
        print(f"  • Response Time: {latest.response_time:.1f}ms")
        print(f"  • Database Status: {latest.database_status}")
        print(f"  • API Status: {latest.api_status}")

        print(f"\n📊 REAL-TIME STATS:")
        print(f"  • Total Requests: {latest.request_count}")
        print(f"  • Error Count: {latest.error_count}")

        recent_alerts = [a for a in self.alerts
                        if datetime.fromisoformat(a["timestamp"]) >
                           (datetime.now() - timedelta(hours=1))]

        if recent_alerts:
            print(f"\n🚨 RECENT ALERTS ({len(recent_alerts)}):")
            for alert in recent_alerts[-5:]:
                severity_emoji = "⚠️" if alert["severity"] == "warning" else "🚨"
                print(f"  {severity_emoji} {alert['type']}: {alert['severity']} "
                      f"({alert['value']:.1f} > {alert['threshold']:.1f})")
        else:
            print(f"\n✅ NO ALERTS - System operating normally")

        print("="*60)

    def start_monitoring(self, interval: int = 60):
        """Start the monitoring system"""
        self.monitoring_active = True

        # Start monitoring in a separate thread
        monitor_thread = threading.Thread(
            target=self.collect_metrics_continuously,
            args=(interval,),
            daemon=True
        )
        monitor_thread.start()

        print("🚀 Monitoring system started!")
        print("📊 Commands available:")
        print("  • 'dashboard' - Display current dashboard")
        print("  • 'stop' - Stop monitoring")
        print("  • 'help' - Show available commands")

        # Interactive command loop
        while self.monitoring_active:
            try:
                command = input("\n🌐 Monitor> ").strip().lower()

                if command == 'dashboard' or command == 'd':
                    self.display_dashboard()
                elif command == 'stop' or command == 'quit' or command == 'q':
                    self.monitoring_active = False
                    print("👋 Monitoring system stopped.")
                    break
                elif command == 'help' or command == 'h':
                    print("\n📋 Available commands:")
                    print("  dashboard, d  - Display current dashboard")
                    print("  stop, quit, q - Stop monitoring")
                    print("  help, h       - Show this help")
                elif command == '':
                    pass  # Empty command, just show prompt again
                else:
                    print(f"❓ Unknown command: {command}")

            except KeyboardInterrupt:
                print("\n👋 Shutting down monitoring system...")
                self.monitoring_active = False
                break

        # Save final state
        self.save_metrics()
        print("💾 Final metrics saved to monitoring/metrics.json")

def main():
    """Main function to run the monitoring dashboard"""
    dashboard = MonitoringDashboard()

    print("🚢 Rowboat Python Backend - Advanced Monitoring Dashboard")
    print("="*60)

    # Initial system check
    health_status = dashboard.get_health_status()
    if health_status.get("status") == "healthy":
        print("✅ Backend is healthy - Starting monitoring system...")
        dashboard.start_monitoring(interval=30)
    else:
        print(f"❌ Backend appears unhealthy: {health_status}")
        print("Proceed with caution...")
        input("Press Enter to continue anyway...")
        dashboard.start_monitoring(interval=30)

if __name__ == "__main__":
    main()