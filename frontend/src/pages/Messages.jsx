import { useState, useEffect } from 'react';
import { Table, Select, Space, Tag, message, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { messagesAPI } from '../services/api';

const { Option } = Select;

function Messages() {
  const [loading, setLoading] = useState(false);
  const [messages_data, setMessages] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [channel, setChannel] = useState(null);

  const fetch = () => {
    setLoading(true);
    messagesAPI.getAll(page, 20, channel)
      .then(r => { setMessages(r.data.messages || []); setTotal(r.data.total || 0); })
      .catch(() => message.error('加载消息日志失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, [page, channel]);

  const cols = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80, render: v => String(v).slice(0, 8) + '...' },
    { title: '渠道', dataIndex: 'channel', key: 'channel', render: v => <Tag color="blue">{v}</Tag> },
    { title: '方向', dataIndex: 'direction', key: 'direction', render: v => <Tag color={v === 'outbound' ? 'green' : 'orange'}>{v === 'outbound' ? '发出' : '接收'}</Tag> },
    { title: '消息类型', dataIndex: 'message_type', key: 'message_type' },
    { title: '用户 ID', dataIndex: 'user_id', key: 'user_id' },
    { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true, width: 200 },
    { title: '状态', dataIndex: 'status', key: 'status' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">消息日志</h1></div>
      <div className="content-wrapper">
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Select placeholder="按渠道筛选" style={{ width: 200 }} allowClear onChange={v => { setChannel(v); setPage(1); }}>
              <Option value="telegram">Telegram</Option>
              <Option value="whatsapp">WhatsApp</Option>
              <Option value="web">Web</Option>
            </Select>
            <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
          </Space>
        </div>
        <Table
          dataSource={messages_data}
          columns={cols}
          loading={loading}
          rowKey="id"
          pagination={{ current: page, pageSize: 20, total, onChange: setPage, showTotal: t => `共 ${t} 条消息` }}
          scroll={{ x: 900 }}
        />
      </div>
    </div>
  );
}

export default Messages;
