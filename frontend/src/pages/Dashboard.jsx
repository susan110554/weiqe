import { useState, useEffect } from 'react';
import { Row, Col, Card, Statistic, Table, Spin, message, Tag } from 'antd';
import { FileTextOutlined, ClockCircleOutlined, CheckCircleOutlined, FileProtectOutlined } from '@ant-design/icons';
import { dashboardAPI } from '../services/api';

function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    dashboardAPI.getStats()
      .then(r => setStats(r.data))
      .catch(() => message.error('加载仪表盘数据失败'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ textAlign: 'center', padding: '100px 0' }}><Spin size="large" /></div>;

  const recentCols = [
    { title: '案件编号', dataIndex: 'case_no', key: 'case_no' },
    { title: '渠道', dataIndex: 'channel', key: 'channel', render: v => <Tag color="blue">{v}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status' },
    { title: '提交时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">控制台</h1></div>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title="案件总数" value={stats?.totals?.cases || 0} prefix={<FileTextOutlined />} valueStyle={{ color: '#1890ff' }} /></Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title="待处理" value={stats?.totals?.pending || 0} prefix={<ClockCircleOutlined />} valueStyle={{ color: '#fa8c16' }} /></Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title="已解决" value={stats?.totals?.resolved || 0} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} /></Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title="消息模板" value={stats?.totals?.templates || 0} prefix={<FileProtectOutlined />} valueStyle={{ color: '#722ed1' }} /></Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="按渠道统计">
            <Table dataSource={stats?.by_channel || []} columns={[{ title: '渠道', dataIndex: 'channel', key: 'channel' }, { title: '数量', dataIndex: 'count', key: 'count' }]} pagination={false} size="small" rowKey="channel" />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="按状态统计">
            <Table dataSource={stats?.by_status || []} columns={[{ title: '状态', dataIndex: 'status', key: 'status' }, { title: '数量', dataIndex: 'count', key: 'count' }]} pagination={false} size="small" rowKey="status" />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card title="最近案件">
            <Table dataSource={stats?.recent_cases || []} columns={recentCols} pagination={false} size="small" rowKey="case_no" />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default Dashboard;
