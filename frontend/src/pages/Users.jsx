import { useState, useEffect } from 'react';
import { Table, Button, Input, Select, Space, Tag, message, Modal, Descriptions, Drawer } from 'antd';
import { SearchOutlined, StopOutlined, CheckCircleOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import { usersAPI } from '../services/api';

const { Option } = Select;

function Users() {
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(null);
  const [detail, setDetail] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const fetch = () => {
    setLoading(true);
    usersAPI.getAll(page, 20, search || undefined, status || undefined)
      .then(r => { setUsers(r.data.users || []); setTotal(r.data.total || 0); })
      .catch(() => message.error('加载用户列表失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, [page, status]);

  const viewDetail = (id) => {
    usersAPI.getOne(id)
      .then(r => { setDetail(r.data); setDrawerOpen(true); })
      .catch(() => message.error('加载失败'));
  };

  const handleBan = (id, isBanned) => Modal.confirm({
    title: isBanned ? '确认解封?' : '确认封禁该用户?',
    onOk: () => (isBanned ? usersAPI.unban(id) : usersAPI.ban(id))
      .then(() => { message.success(isBanned ? '已解封' : '已封禁'); fetch(); })
      .catch(() => message.error('操作失败'))
  });

  const cols = [
    { title: '用户 ID', dataIndex: 'tg_user_id', key: 'tg_user_id' },
    { title: '用户名', dataIndex: 'tg_username', key: 'tg_username', render: v => v || '-' },
    { title: '状态', dataIndex: 'status', key: 'status', render: v => <Tag color={v === 'active' ? 'green' : v === 'banned' ? 'red' : 'default'}>{v === 'active' ? '正常' : v === 'banned' ? '封禁' : '正常'}</Tag> },
    { title: '语言', dataIndex: 'language_code', key: 'language_code' },
    { title: '注册时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', render: (_, r) => (
      <Space>
        <Button type="link" icon={<EyeOutlined />} onClick={() => viewDetail(r.tg_user_id)}>查看</Button>
        <Button type="link" danger={r.status !== 'banned'} icon={r.status === 'banned' ? <CheckCircleOutlined /> : <StopOutlined />}
          onClick={() => handleBan(r.tg_user_id, r.status === 'banned')}>
          {r.status === 'banned' ? '解封' : '封禁'}
        </Button>
      </Space>
    )},
  ];

  const caseCols = [
    { title: '案件编号', dataIndex: 'case_no', key: 'case_no' },
    { title: '状态', dataIndex: 'status', key: 'status', render: v => <Tag color="blue">{v}</Tag> },
    { title: '提交时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">用户管理</h1></div>
      <div className="content-wrapper">
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Input.Search placeholder="搜索 ID 或用户名" style={{ width: 250 }}
              onSearch={v => { setSearch(v); setPage(1); fetch(); }} allowClear />
            <Select placeholder="状态筛选" style={{ width: 160 }} allowClear onChange={v => { setStatus(v); setPage(1); }}>
              <Option value="active">正常</Option>
              <Option value="banned">封禁</Option>
            </Select>
            <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
          </Space>
        </div>
        <Table dataSource={users} columns={cols} loading={loading} rowKey="tg_user_id"
          pagination={{ current: page, pageSize: 20, total, onChange: setPage, showTotal: t => `共 ${t} 条` }} />
      </div>

      <Drawer title={`用户详情：${detail?.tg_user_id}`} open={drawerOpen} onClose={() => setDrawerOpen(false)} width={500}>
        {detail && (
          <>
            <Descriptions column={1} bordered size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="用户 ID">{detail.tg_user_id}</Descriptions.Item>
              <Descriptions.Item label="用户名">{detail.tg_username || '-'}</Descriptions.Item>
              <Descriptions.Item label="状态"><Tag color={detail.status === 'banned' ? 'red' : 'green'}>{detail.status === 'banned' ? '封禁' : '正常'}</Tag></Descriptions.Item>
              <Descriptions.Item label="语言">{detail.language_code || '-'}</Descriptions.Item>
              <Descriptions.Item label="注册时间">{detail.created_at ? new Date(detail.created_at).toLocaleString('zh-CN') : '-'}</Descriptions.Item>
            </Descriptions>
            <h4>关联案件 ({detail.cases?.length || 0})</h4>
            <Table dataSource={detail.cases || []} columns={caseCols} rowKey="case_no" size="small" pagination={false} />
          </>
        )}
      </Drawer>
    </div>
  );
}

export default Users;
