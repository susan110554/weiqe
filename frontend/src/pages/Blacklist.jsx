import { useState, useEffect } from 'react';
import { Table, Button, Space, Tag, message, Modal, Form, Input, Select, Tabs } from 'antd';
import { PlusOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { blacklistAPI } from '../services/api';

const { Option } = Select;

function Blacklist() {
  const [loading, setLoading] = useState(false);
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const fetch = () => {
    setLoading(true);
    blacklistAPI.getAll(page, 20)
      .then(r => { setEntries(r.data.entries || []); setTotal(r.data.total || 0); })
      .catch(() => message.error('加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, [page]);

  const handleDelete = (id) => Modal.confirm({
    title: '从黑名单移除?',
    onOk: () => blacklistAPI.remove(id).then(() => { message.success('已移除'); fetch(); }).catch(() => message.error('操作失败')),
  });

  const handleAdd = async (values) => {
    try {
      await blacklistAPI.add(values);
      message.success('已添加到黑名单');
      setModalOpen(false);
      form.resetFields();
      fetch();
    } catch { message.error('操作失败'); }
  };

  const cols = [
    { title: '用户 ID', dataIndex: 'tg_user_id', key: 'tg_user_id', render: v => v || '-' },
    { title: '钱包地址', dataIndex: 'wallet_address', key: 'wallet_address', render: v => v ? <code style={{ fontSize: 11 }}>{v}</code> : '-' },
    { title: '链', dataIndex: 'chain', key: 'chain', render: v => v ? <Tag color="purple">{v}</Tag> : '-' },
    { title: '原因', dataIndex: 'reason', key: 'reason', ellipsis: true },
    { title: '创建人', dataIndex: 'created_by', key: 'created_by' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', render: (_, r) => (
      <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)}>移除</Button>
    )},
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">黑名单管理</h1></div>
      <div className="content-wrapper">
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
          <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>添加到黑名单</Button>
        </div>
        <Table dataSource={entries} columns={cols} loading={loading} rowKey="id"
          pagination={{ current: page, pageSize: 20, total, onChange: setPage, showTotal: t => `共 ${t} 条` }} />
      </div>

      <Modal title="添加到黑名单" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleAdd}>
          <Form.Item label="Telegram 用户 ID" name="tg_user_id" extra="输入要封禁的用户 ID"><Input type="number" /></Form.Item>
          <Form.Item label="钱包地址" name="wallet_address"><Input placeholder="0x... 或 T..." /></Form.Item>
          <Form.Item label="链" name="chain">
            <Select allowClear>
              <Option value="ETH">以太坊</Option>
              <Option value="BSC">币安智能链</Option>
              <Option value="TRX">波场</Option>
              <Option value="BTC">比特币</Option>
            </Select>
          </Form.Item>
          <Form.Item label="标签/原因" name="reason"><Input /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default Blacklist;
