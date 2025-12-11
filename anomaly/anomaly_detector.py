import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from datetime import datetime, timedelta
import sqlite3
from typing import List, Dict, Tuple

DB_NAME = "monitor.db"


class AnomalyDetector:
    def __init__(self, contamination=0.1):
        """
        Initialize anomaly detector with both statistical and ML methods

        Args:
            contamination: Expected proportion of outliers (default 10%)
        """
        self.contamination = contamination
        self.isolation_forest = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.lof = LocalOutlierFactor(
            contamination=contamination,
            novelty=True,
            n_neighbors=20
        )
        self.trained = False

    def get_recent_metrics(self, device_id: int, hours: int = 24) -> List[Dict]:
        """Get metrics for a device from the last N hours"""
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

        rows = c.execute('''
                         SELECT *
                         FROM metrics_logs
                         WHERE device_id = ? AND timestamp > ?
                         ORDER BY timestamp ASC
                         ''', (device_id, cutoff_time)).fetchall()

        conn.close()
        return [dict(row) for row in rows]

    def prepare_features(self, metrics: List[Dict]) -> np.ndarray:
        """Extract feature matrix from metrics"""
        features = []
        for m in metrics:
            features.append([
                m.get('cpu', 0) or 0,
                m.get('ram', 0) or 0,
                m.get('disk', 0) or 0,
                m.get('net_sent', 0) or 0,
                m.get('net_recv', 0) or 0
            ])
        return np.array(features)

    def detect_zscore_anomalies(self, metrics: List[Dict], threshold: float = 3.0) -> List[Dict]:
        """
        Detect anomalies using Z-score method
        Returns list of anomalies with details
        """
        if len(metrics) < 10:
            return []

        features = self.prepare_features(metrics)
        anomalies = []

        # Calculate z-scores for each metric
        mean = np.mean(features, axis=0)
        std = np.std(features, axis=0)

        # Avoid division by zero
        std = np.where(std == 0, 1, std)

        z_scores = np.abs((features - mean) / std)

        metric_names = ['cpu', 'ram', 'disk', 'net_sent', 'net_recv']

        for i, (metric, z_score_row) in enumerate(zip(metrics, z_scores)):
            anomalous_metrics = []
            for j, z in enumerate(z_score_row):
                if z > threshold:
                    anomalous_metrics.append({
                        'metric': metric_names[j],
                        'value': features[i][j],
                        'z_score': float(z),
                        'mean': float(mean[j]),
                        'std': float(std[j])
                    })

            if anomalous_metrics:
                anomalies.append({
                    'timestamp': metric['timestamp'],
                    'device_id': metric['device_id'],
                    'method': 'z-score',
                    'anomalous_metrics': anomalous_metrics,
                    'severity': 'high' if max(m['z_score'] for m in anomalous_metrics) > 4 else 'medium'
                })

        return anomalies

    def detect_moving_average_anomalies(self, metrics: List[Dict],
                                        window: int = 10,
                                        threshold: float = 2.0) -> List[Dict]:
        """
        Detect anomalies using moving average and standard deviation
        """
        if len(metrics) < window + 5:
            return []

        features = self.prepare_features(metrics)
        anomalies = []
        metric_names = ['cpu', 'ram', 'disk', 'net_sent', 'net_recv']

        for i in range(window, len(features)):
            window_data = features[i - window:i]
            current = features[i]

            moving_avg = np.mean(window_data, axis=0)
            moving_std = np.std(window_data, axis=0)
            moving_std = np.where(moving_std == 0, 1, moving_std)

            deviations = np.abs((current - moving_avg) / moving_std)

            anomalous_metrics = []
            for j, dev in enumerate(deviations):
                if dev > threshold:
                    anomalous_metrics.append({
                        'metric': metric_names[j],
                        'value': float(current[j]),
                        'deviation': float(dev),
                        'moving_avg': float(moving_avg[j]),
                        'moving_std': float(moving_std[j])
                    })

            if anomalous_metrics:
                anomalies.append({
                    'timestamp': metrics[i]['timestamp'],
                    'device_id': metrics[i]['device_id'],
                    'method': 'moving_average',
                    'anomalous_metrics': anomalous_metrics,
                    'severity': 'high' if max(m['deviation'] for m in anomalous_metrics) > 3 else 'medium'
                })

        return anomalies

    def detect_ml_anomalies(self, metrics: List[Dict], method: str = 'isolation_forest') -> List[Dict]:
        """
        Detect anomalies using machine learning methods
        Methods: 'isolation_forest' or 'lof'
        """
        if len(metrics) < 50:  # Need enough data for ML
            return []

        features = self.prepare_features(metrics)

        try:
            if method == 'isolation_forest':
                if not self.trained:
                    self.isolation_forest.fit(features)
                predictions = self.isolation_forest.predict(features)
                scores = self.isolation_forest.score_samples(features)
            else:  # LOF
                if not self.trained:
                    self.lof.fit(features)
                predictions = self.lof.predict(features)
                scores = self.lof.score_samples(features)

            self.trained = True

            anomalies = []
            for i, (pred, score) in enumerate(zip(predictions, scores)):
                if pred == -1:  # Anomaly detected
                    anomalies.append({
                        'timestamp': metrics[i]['timestamp'],
                        'device_id': metrics[i]['device_id'],
                        'method': method,
                        'anomaly_score': float(score),
                        'metrics_snapshot': {
                            'cpu': metrics[i].get('cpu'),
                            'ram': metrics[i].get('ram'),
                            'disk': metrics[i].get('disk'),
                            'net_sent': metrics[i].get('net_sent'),
                            'net_recv': metrics[i].get('net_recv')
                        },
                        'severity': 'high' if score < -0.5 else 'medium'
                    })

            return anomalies

        except Exception as e:
            print(f"ML anomaly detection error: {e}")
            return []

    def detect_all_anomalies(self, device_id: int) -> Dict[str, List[Dict]]:
        """
        Run all anomaly detection methods and return combined results
        """
        metrics = self.get_recent_metrics(device_id, hours=24)

        if not metrics:
            return {}

        results = {
            'z_score': self.detect_zscore_anomalies(metrics),
            'moving_average': self.detect_moving_average_anomalies(metrics),
            'isolation_forest': self.detect_ml_anomalies(metrics, 'isolation_forest'),
            'lof': self.detect_ml_anomalies(metrics, 'lof')
        }

        return results

    def get_anomaly_summary(self, device_id: int) -> Dict:
        """
        Get a summary of all detected anomalies
        """
        all_anomalies = self.detect_all_anomalies(device_id)

        total_count = sum(len(anomalies) for anomalies in all_anomalies.values())

        high_severity = sum(
            1 for method_anomalies in all_anomalies.values()
            for anomaly in method_anomalies
            if anomaly.get('severity') == 'high'
        )

        return {
            'device_id': device_id,
            'total_anomalies': total_count,
            'high_severity_count': high_severity,
            'medium_severity_count': total_count - high_severity,
            'by_method': {
                method: len(anomalies)
                for method, anomalies in all_anomalies.items()
            },
            'detailed_anomalies': all_anomalies
        }


def save_anomaly_to_db(anomaly: Dict):
    """Save detected anomaly to database for logging"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Create anomalies table if it doesn't exist
    c.execute('''
              CREATE TABLE IF NOT EXISTS anomalies
              (
                  id
                  INTEGER
                  PRIMARY
                  KEY
                  AUTOINCREMENT,
                  timestamp
                  TEXT
                  NOT
                  NULL,
                  device_id
                  INTEGER
                  NOT
                  NULL,
                  detection_method
                  TEXT
                  NOT
                  NULL,
                  severity
                  TEXT
                  NOT
                  NULL,
                  details
                  TEXT
                  NOT
                  NULL,
                  acknowledged
                  INTEGER
                  DEFAULT
                  0,
                  FOREIGN
                  KEY
              (
                  device_id
              ) REFERENCES devices
              (
                  id
              )
                  )
              ''')

    import json
    c.execute('''
              INSERT INTO anomalies (timestamp, device_id, detection_method, severity, details)
              VALUES (?, ?, ?, ?, ?)
              ''', (
                  anomaly['timestamp'],
                  anomaly['device_id'],
                  anomaly['method'],
                  anomaly['severity'],
                  json.dumps(anomaly)
              ))

    conn.commit()
    conn.close()


def get_all_anomalies(limit: int = 100, device_id: int = None):
    """Retrieve anomalies from database"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if device_id:
        rows = c.execute('''
                         SELECT *
                         FROM anomalies
                         WHERE device_id = ?
                         ORDER BY id DESC LIMIT ?
                         ''', (device_id, limit)).fetchall()
    else:
        rows = c.execute('''
                         SELECT *
                         FROM anomalies
                         ORDER BY id DESC LIMIT ?
                         ''', (limit,)).fetchall()

    conn.close()
    return [dict(row) for row in rows]