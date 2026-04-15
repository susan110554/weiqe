import { useState, useEffect } from 'react';
import { Table, Card, Tag, Button, message, Drawer, List, Badge } from 'antd';
import { InboxOutlined, ReloadOutlined } from '@ant-design/icons';
import { agentsAPI } from '../services/api';

function Agents() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [inbox, setInbox] = useState([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState(null);

  const fetch = () => {
    setLoading(true);
    agentsAPI.getAll()
      .then(r => setAgents(r.data.agents || []))
      .catch(() => message.error('加载探员列表失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, []);

  const viewInbox = (agent) => {
    setSelectedAgent(agent);
    agentsAPI.getInbox(agent.agent_code)
      .then(r => { setInbox(r.data.inbox || []); setDrawerOpen(true); })
      .catch(() => message.error('加载收件符1失败'));
  };

  const cols = [
    { title: '探员代号', dataIndex: 'agent_code', key: 'agent_code', render: v => <Tag color="blue">{v}</Tag> },
    { title: '姓名', dataIndex: 'name', key: 'name' },
    { title: '状态', dataIndex: 'status', key: 'status', render: v => <Badge status={v === 'active' ? 'success' : 'default'} text={v === 'active' ? '在线' : '离线'} /> },
    { title: '负责案件', dataIndex: 'active_cases', key: 'active_cases', render: v => v || 0 },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', render: (_, r) => (
      <Button type="link" icon={<InboxOutlined />} onClick={() => viewInbox(r)}>收件符号</Button>
    )},
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">探员管理</h1></div>
      <div className="content-wrapper">
        <div style={{ marginBottom: 16 }}>
          <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
        </div>
        <Table dataSource={agents} columns={cols} loading={loading} rowKey="agent_code" pagination={{ pageSize: 20 }} />
      </div>

      <Drawer title={`收件符号：${selectedAgent?.agent_code}`} open={drawerOpen} onClose={() => setDrawerOpen(false)} width={480}>
        <List dataSource={inbox} renderItem={item => (
          <List.Item>
            <List.Item.Meta
              title={<span><Tag color="blue">{item.case_no}</Tag> {item.message_type}</span>}
              description={<><div>{item.content}</div><div style={{ fontSize: 11, color: '#999' }}>{item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : ''}</div></>}
            />
          </List.Item>
        )} />
      </Drawer>
    </div>
  );
}

export default Agents;
