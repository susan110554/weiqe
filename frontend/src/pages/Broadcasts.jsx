import { useState, useEffect } from 'react';
import { Table, Button, Select, Space, Tag, message, Modal, Form, Input } from 'antd';
import { PlusOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { broadcastsAPI } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;

const statusColor = { pending: 'orange', sent: 'green', failed: 'red', cancelled: 'default' };

function Broadcasts() {
  const [loading, setLoading] = useState(false);
  const [broadcasts, setBroadcasts] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();

  const fetch = () => {
    setLoading(true);
    broadcastsAPI.getAll(page, 20)
      .then(r => { setBroadcasts(r.data.broadcasts || []); setTotal(r.data.total || 0); })
      .catch(() => message.error('加载广播列表失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, [page]);

  const handleDelete = (id) => Modal.confirm({
    title: '确认删除',
    content: '确定删除此广播?',
    onOk: () => broadcastsAPI.delete(id)
      .then(() => { message.success('已删除'); fetch(); })
      .catch(() => message.error('删除失败')),
  });

  const handleCreate = async (values) => {
    try {
      await broadcastsAPI.create(values);
      message.success('广播已创建');
      setModalVisible(false);
      form.resetFields();
      fetch();
    } catch (e) {
      message.error(e.response?.data?.detail || '创建失败');
    }
  };

  const cols = [
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '渠道', dataIndex: 'channel', key: 'channel', render: v => <Tag color="blue">{v}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', render: v => <Tag color={statusColor[v] || 'default'}>{v}</Tag> },
    { title: '计划发送时间', dataIndex: 'scheduled_at', key: 'scheduled_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '立即发送', },
    { title: '创建人', dataIndex: 'created_by', key: 'created_by' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', render: (_, r) => (
      <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)}>删除</Button>
    )},
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">广播管理</h1></div>
      <div className="content-wrapper">
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
          <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>创建广播</Button>
        </div>
        <Table
          dataSource={broadcasts}
          columns={cols}
          loading={loading}
          rowKey="id"
          pagination={{ current: page, pageSize: 20, total, onChange: setPage, showTotal: t => `共 ${t} 条` }}
        />
      </div>

      <Modal title="创建广播" open={modalVisible} onCancel={() => setModalVisible(false)} onOk={() => form.submit()} width={600}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item label="标题" name="title" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="渠道" name="channel" rules={[{ required: true }]}>
            <Select>
              <Option value="telegram">Telegram</Option>
              <Option value="whatsapp">WhatsApp</Option>
              <Option value="all">所有渠道</Option>
            </Select>
          </Form.Item>
          <Form.Item label="内容" name="content" rules={[{ required: true }]}><TextArea rows={5} /></Form.Item>
          <Form.Item label="计划发送时间 (可选)" name="scheduled_at" extra="留空表示立即发送">
            <Input placeholder="2026-04-20T10:00:00" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default Broadcasts;
