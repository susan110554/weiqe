import { useState, useEffect } from 'react';
import { Table, Button, Input, Select, Space, Tag, message, Modal } from 'antd';
import { ReloadOutlined, ExportOutlined } from '@ant-design/icons';
import { auditAPI } from '../services/api';

const { Option } = Select;

function AuditLogs() {
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [actionType, setActionType] = useState(null);
  const [actorId, setActorId] = useState('');
  const [detail, setDetail] = useState(null);

  const fetch = () => {
    setLoading(true);
    auditAPI.getLogs(page, 20, actionType || undefined, actorId || undefined)
      .then(r => { setLogs(r.data.logs || []); setTotal(r.data.total || 0); })
      .catch(() => message.error('加载审计日志失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, [page, actionType]);

  const exportCSV = () => {
    const headers = ['Time', 'Actor', 'Action Type', 'Target', 'IP'];
    const rows = logs.map(l => [l.created_at, l.actor_id, l.action_type, l.target_id, l.ip_address].join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'audit_logs.csv'; a.click();
  };

  const cols = [
    { title: '操作时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作人', dataIndex: 'actor_id', key: 'actor_id', width: 120 },
    { title: '操作人类型', dataIndex: 'actor_type', key: 'actor_type', width: 100,
      render: v => <Tag color={v === 'admin' ? 'blue' : 'default'}>{v === 'admin' ? '管理员' : '系统'}</Tag> },
    { title: '操作类型', dataIndex: 'action_type', key: 'action_type', width: 160,
      render: v => <Tag color="orange">{v}</Tag> },
    { title: '操作目标', dataIndex: 'target_id', key: 'target_id', width: 120 },
    { title: '摘要', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: 'IP 地址', dataIndex: 'ip_address', key: 'ip_address', width: 130 },
    { title: '详情', key: 'detail', width: 80,
      render: (_, r) => r.extra_data ? <Button type="link" size="small" onClick={() => setDetail(r)}>查看</Button> : '-' },
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">审计日志</h1></div>
      <div className="content-wrapper">
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
          <Space>
            <Select placeholder="操作类型" style={{ width: 180 }} allowClear onChange={v => { setActionType(v); setPage(1); }}>
              <Option value="login">登录</Option>
              <Option value="case_update">案件更新</Option>
              <Option value="template_update">模板编辑</Option>
              <Option value="user_ban">用户封禁</Option>
              <Option value="config_update">配置更新</Option>
            </Select>
            <Input.Search placeholder="操作人 ID" style={{ width: 180 }}
              onSearch={v => { setActorId(v); fetch(); }} allowClear />
            <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
          </Space>
          <Button icon={<ExportOutlined />} onClick={exportCSV}>导出 CSV</Button>
        </div>
        <Table dataSource={logs} columns={cols} loading={loading} rowKey="id"
          pagination={{ current: page, pageSize: 20, total, onChange: setPage, showTotal: t => `共 ${t} 条` }}
          scroll={{ x: 900 }} />
      </div>

      <Modal title="日志详情" open={!!detail} onCancel={() => setDetail(null)} footer={null} width={600}>
        {detail && (
          <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 8, overflow: 'auto', maxHeight: 400 }}>
            {JSON.stringify(detail, null, 2)}
          </pre>
        )}
      </Modal>
    </div>
  );
}

export default AuditLogs;
