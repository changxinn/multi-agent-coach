import { useState } from 'react'
import { Table, Tag, Space, Button, Input, Select, Card, Typography, Popconfirm, message, Badge } from 'antd'
import {
  SearchOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ExportOutlined,
  FilterOutlined,
} from '@ant-design/icons'
import { Status, getStatusColor } from '@/lib/constants'
import type { ColumnsType } from 'antd/es/table'

const { Title, Text } = Typography
const { Option } = Select

interface Employee {
  key: string
  id: string
  name: string
  email: string
  department: string
  role: string
  status: 'active' | 'inactive' | 'on-leave'
  joinDate: string
  location: string
}

const sampleData: Employee[] = [
  { key: '1', id: 'EMP001', name: 'John Smith', email: 'john.smith@company.com', department: 'Engineering', role: 'Senior Developer', status: Status.Active, joinDate: '2022-03-15', location: 'New York' },
  { key: '2', id: 'EMP002', name: 'Sarah Johnson', email: 'sarah.j@company.com', department: 'Marketing', role: 'Marketing Manager', status: Status.Active, joinDate: '2021-07-22', location: 'London' },
  { key: '3', id: 'EMP003', name: 'Michael Chen', email: 'm.chen@company.com', department: 'Engineering', role: 'Tech Lead', status: Status.Active, joinDate: '2020-01-10', location: 'San Francisco' },
  { key: '4', id: 'EMP004', name: 'Emily Davis', email: 'emily.d@company.com', department: 'HR', role: 'HR Specialist', status: Status.OnLeave, joinDate: '2023-02-28', location: 'New York' },
  { key: '5', id: 'EMP005', name: 'David Wilson', email: 'd.wilson@company.com', department: 'Sales', role: 'Sales Representative', status: Status.Active, joinDate: '2022-11-05', location: 'Chicago' },
  { key: '6', id: 'EMP006', name: 'Lisa Anderson', email: 'lisa.a@company.com', department: 'Finance', role: 'Financial Analyst', status: Status.Active, joinDate: '2021-09-14', location: 'Boston' },
  { key: '7', id: 'EMP007', name: 'James Brown', email: 'j.brown@company.com', department: 'Engineering', role: 'Junior Developer', status: Status.Inactive, joinDate: '2023-06-01', location: 'Remote' },
  { key: '8', id: 'EMP008', name: 'Jennifer Lee', email: 'j.lee@company.com', department: 'Product', role: 'Product Manager', status: Status.Active, joinDate: '2020-05-20', location: 'San Francisco' },
  { key: '9', id: 'EMP009', name: 'Robert Taylor', email: 'r.taylor@company.com', department: 'Operations', role: 'Operations Manager', status: Status.Active, joinDate: '2019-08-12', location: 'London' },
  { key: '10', id: 'EMP010', name: 'Maria Garcia', email: 'm.garcia@company.com', department: 'Marketing', role: 'Content Specialist', status: Status.OnLeave, joinDate: '2022-04-18', location: 'Madrid' },
]

export function TableListingPage() {
  const [searchText, setSearchText] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState<string>('all')
  const [data, setData] = useState<Employee[]>(sampleData)

  const handleDelete = (id: string) => {
    setData(data.filter(item => item.id !== id))
    message.success('Employee deleted successfully')
  }

  const handleExport = () => {
    message.info('Exporting data to CSV...')
    console.log('Export data:', data)
  }

  const columns: ColumnsType<Employee> = [
    {
      title: 'Employee ID',
      dataIndex: 'id',
      key: 'id',
      sorter: (a, b) => a.id.localeCompare(b.id),
      width: 100,
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
      render: (name) => <Text strong>{name}</Text>,
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      ellipsis: true,
    },
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
      filters: [
        { text: 'Engineering', value: 'Engineering' },
        { text: 'Marketing', value: 'Marketing' },
        { text: 'HR', value: 'HR' },
        { text: 'Sales', value: 'Sales' },
        { text: 'Finance', value: 'Finance' },
        { text: 'Product', value: 'Product' },
        { text: 'Operations', value: 'Operations' },
      ],
      onFilter: (value, record) => record.department === value,
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: Status) => (
        <Badge
          status={getStatusColor(status) as any}
          text={status.charAt(0).toUpperCase() + status.slice(1).replace('-', ' ')}
        />
      ),
      filters: [
        { text: 'Active', value: Status.Active },
        { text: 'Inactive', value: Status.Inactive },
        { text: 'On Leave', value: Status.OnLeave },
      ],
      onFilter: (value, record) => record.status === value,
    },
    {
      title: 'Location',
      dataIndex: 'location',
      key: 'location',
    },
    {
      title: 'Join Date',
      dataIndex: 'joinDate',
      key: 'joinDate',
      sorter: (a, b) => new Date(a.joinDate).getTime() - new Date(b.joinDate).getTime(),
      render: (date) => new Date(date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />}>
            Edit
          </Button>
          <Popconfirm
            title="Delete Employee"
            description="Are you sure you want to delete this employee?"
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const filteredData = data.filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(searchText.toLowerCase()) ||
                         item.email.toLowerCase().includes(searchText.toLowerCase()) ||
                         item.id.toLowerCase().includes(searchText.toLowerCase())
    const matchesDepartment = departmentFilter === 'all' || item.department === departmentFilter
    return matchesSearch && matchesDepartment
  })

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <Title level={2} className="mb-2">Employee Directory</Title>
          <Text type="secondary">Manage and view all employees in the organization</Text>
        </div>
        <Button type="primary" icon={<ExportOutlined />} onClick={handleExport}>
          Export
        </Button>
      </div>

      <Card className="mb-6">
        <Space className="w-full" orientation="vertical" size="middle">
          <div className="flex gap-4 flex-wrap">
            <Input
              placeholder="Search by name, email, or ID"
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ width: 300 }}
              allowClear
            />
            <Select
              placeholder="Filter by Department"
              value={departmentFilter}
              onChange={setDepartmentFilter}
              style={{ width: 200 }}
              allowClear
            >
              <Option value="all">All Departments</Option>
              <Option value="Engineering">Engineering</Option>
              <Option value="Marketing">Marketing</Option>
              <Option value="HR">HR</Option>
              <Option value="Sales">Sales</Option>
              <Option value="Finance">Finance</Option>
              <Option value="Product">Product</Option>
              <Option value="Operations">Operations</Option>
            </Select>
            <Button icon={<FilterOutlined />}>More Filters</Button>
          </div>
        </Space>
      </Card>

      <Card>
        <div className="flex justify-between items-center mb-4">
          <Text strong>Total Employees: {filteredData.length}</Text>
          <Button type="primary" icon={<PlusOutlined />}>
            Add Employee
          </Button>
        </div>
        <Table
          columns={columns}
          dataSource={filteredData}
          pagination={{
            pageSize: 5,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} employees`,
          }}
          rowSelection={{
            type: 'checkbox',
          }}
          scroll={{ x: 1200 }}
        />
      </Card>
    </div>
  )
}

export default TableListingPage
