import { useState, useEffect } from 'react';
import { Table, Button, Tag, message, Card, Row, Col, Statistic } from 'antd';
import { ReloadOutlined, UserOutlined, SafetyOutlined, TeamOutlined } from '@ant-design/icons';
import { adminsAPI } from '../services/api';

const ROLE_COLOR = { L1: 'red', L2: 'orange', L3: 'blue' };
const ROLE_LABEL = { L1: 'L1 超级管理员', L2: 'L2 管理员', L3: 'L3 探员' };
const ROLE_PERMS = {
  L1: ['所有功能的完全访问权限', '管理 L2/L3 管理员', '系统配置', '查看所有审计日志'],
  L2: ['案件管理 (P1-P12)', '用户管理', '模板编辑', '费用配置'],
  L3: ['查看分配的案件', '向用户发送消息', '更新案件备注', '查看案件历史'],
};

function AdminManagement() {
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetch = () => {
    setLoading(true);
    adminsAPI.getAll()
      .then(r => setAdmins(r.data.admins || []))
      .catch(() => message.error('加载管理员列表失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, []);

  const cols = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email', render: v => v || '-' },
    { title: '角色', dataIndex: 'role', key: 'role', render: v => <Tag color={ROLE_COLOR[v] || 'default'}>{ROLE_LABEL[v] || v}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', render: v => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '正常' : '停用'}</Tag>, },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">管理员管理</h1></div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {Object.entries(ROLE_PERMS).map(([role, perms]) => (
          <Col xs={24} md={8} key={role}>
            <Card title={<><Tag color={ROLE_COLOR[role]}>{role}</Tag> {ROLE_LABEL[role]}</>} size="small">
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {perms.map((p, i) => <li key={i} style={{ fontSize: 12, color: '#555' }}>{p}</li>)}
              </ul>
            </Card>
          </Col>
        ))}
      </Row>

      <div className="content-wrapper">
        <div style={{ marginBottom: 16 }}>
          <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
        </div>
        <Table dataSource={admins} columns={cols} loading={loading} rowKey="id"
          pagination={{ pageSize: 20 }} />
      </div>
    </div>
  );
}

export default AdminManagement;
