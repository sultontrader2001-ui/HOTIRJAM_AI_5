#region Using declarations
using System;
using System.IO;
using System.Net.Sockets;
using System.Threading;
#endregion

// HOTIRJAM Gateway — TCP client to Python Gateway transport (Sprint NT-1.1).
// Connect / Disconnect / Auto-reconnect.
// No Heartbeat. No Tick. No DOM. No Orders. No Broker API. No Trading Logic.

namespace HOTIRJAM.Gateway
{
	/// <summary>
	/// TCP client for the Python <c>TransportServer</c> (NDJSON line protocol).
	/// This sprint only maintains the socket link — no market or order payloads.
	/// </summary>
	public sealed class GatewayClient : IDisposable
	{
		public const string DefaultHost = "127.0.0.1";
		public const int DefaultPort = 8765;
		public const int DefaultReconnectDelayMs = 2000;
		public const int DefaultConnectTimeoutMs = 5000;
		private const int ReceivePollMs = 500;
		private const int ReceiveBufferSize = 4096;

		private readonly string _host;
		private readonly int _port;
		private readonly int _reconnectDelayMs;
		private readonly int _connectTimeoutMs;
		private readonly Action<string> _log;
		private readonly object _gate = new object();
		private readonly byte[] _recvBuffer = new byte[ReceiveBufferSize];

		private TcpClient _tcp;
		private Thread _worker;
		private volatile bool _run;
		private volatile bool _started;
		private volatile bool _disposed;
		private volatile bool _connected;

		public GatewayClient(string host, int port, Action<string> log)
			: this(host, port, log, DefaultReconnectDelayMs, DefaultConnectTimeoutMs)
		{
		}

		public GatewayClient(
			string host,
			int port,
			Action<string> log,
			int reconnectDelayMs,
			int connectTimeoutMs)
		{
			if (string.IsNullOrWhiteSpace(host))
				throw new ArgumentException("host is required", "host");
			if (port <= 0 || port > 65535)
				throw new ArgumentOutOfRangeException("port");
			if (reconnectDelayMs < 100)
				throw new ArgumentOutOfRangeException("reconnectDelayMs");
			if (connectTimeoutMs < 100)
				throw new ArgumentOutOfRangeException("connectTimeoutMs");

			_host = host.Trim();
			_port = port;
			_log = log;
			_reconnectDelayMs = reconnectDelayMs;
			_connectTimeoutMs = connectTimeoutMs;
		}

		public string Host
		{
			get { return _host; }
		}

		public int Port
		{
			get { return _port; }
		}

		/// <summary>True while the auto-reconnect supervisor is running.</summary>
		public bool IsStarted
		{
			get { return _started; }
		}

		/// <summary>True while a TCP session to the Python Gateway is open.</summary>
		public bool IsConnected
		{
			get { return _connected; }
		}

		/// <summary>
		/// Start the background supervisor: connect, then auto-reconnect on drop.
		/// </summary>
		public void Start()
		{
			ThrowIfDisposed();
			lock (_gate)
			{
				if (_started)
					return;

				_run = true;
				_started = true;
				_worker = new Thread(ReconnectLoop)
				{
					IsBackground = true,
					Name = "HOTIRJAM-GatewayClient"
				};
				_worker.Start();
			}
			Log("HOTIRJAM GatewayClient Start host=" + _host + " port=" + _port);
		}

		/// <summary>
		/// Stop auto-reconnect and disconnect.
		/// </summary>
		public void Stop()
		{
			if (_disposed)
				return;

			Thread worker;
			lock (_gate)
			{
				_run = false;
				worker = _worker;
				_worker = null;
			}

			Disconnect();

			if (worker != null && worker.IsAlive && Thread.CurrentThread != worker)
			{
				try
				{
					worker.Join(5000);
				}
				catch
				{
					// Ignore join failures on shutdown.
				}
			}

			lock (_gate)
			{
				_started = false;
			}

			Log("HOTIRJAM GatewayClient Stop");
		}

		/// <summary>
		/// Attempt a single TCP connect. Returns true on success.
		/// If <see cref="Start"/> is running, prefer letting the supervisor connect.
		/// </summary>
		public bool Connect()
		{
			ThrowIfDisposed();
			return TryConnect();
		}

		/// <summary>
		/// Close the current TCP session. If <see cref="Start"/> is running, auto-reconnect follows.
		/// </summary>
		public void Disconnect()
		{
			TcpClient tcp;
			lock (_gate)
			{
				tcp = _tcp;
				_tcp = null;
				_connected = false;
			}

			if (tcp == null)
				return;

			try
			{
				tcp.Close();
			}
			catch
			{
				// Ignore close races.
			}

			Log("HOTIRJAM GatewayClient Disconnect");
		}

		public void Dispose()
		{
			if (_disposed)
				return;

			Stop();
			_disposed = true;
		}

		private void ReconnectLoop()
		{
			while (_run && !_disposed)
			{
				if (!TryConnect())
				{
					SleepInterruptible(_reconnectDelayMs);
					continue;
				}

				MonitorConnection();
				Disconnect();

				if (!_run || _disposed)
					break;

				Log("HOTIRJAM GatewayClient Reconnecting in " + _reconnectDelayMs + "ms");
				SleepInterruptible(_reconnectDelayMs);
			}
		}

		private bool TryConnect()
		{
			if (_disposed)
				return false;

			lock (_gate)
			{
				if (_tcp != null && _connected)
					return true;
			}

			TcpClient tcp = null;
			try
			{
				tcp = new TcpClient();
				IAsyncResult ar = tcp.BeginConnect(_host, _port, null, null);
				bool signaled = ar.AsyncWaitHandle.WaitOne(_connectTimeoutMs);
				if (!signaled)
				{
					try { tcp.Close(); } catch { }
					Log("HOTIRJAM GatewayClient Connect timeout host=" + _host + " port=" + _port);
					return false;
				}

				tcp.EndConnect(ar);
				tcp.NoDelay = true;
				tcp.Client.ReceiveTimeout = ReceivePollMs;

				lock (_gate)
				{
					if (_disposed || (_started && !_run))
					{
						try { tcp.Close(); } catch { }
						return false;
					}

					TcpClient old = _tcp;
					_tcp = tcp;
					_connected = true;
					tcp = null;
					if (old != null)
					{
						try { old.Close(); } catch { }
					}
				}

				Log("HOTIRJAM GatewayClient Connect ok host=" + _host + " port=" + _port);
				return true;
			}
			catch (Exception ex)
			{
				if (tcp != null)
				{
					try { tcp.Close(); } catch { }
				}
				Log("HOTIRJAM GatewayClient Connect failed: " + ex.Message);
				return false;
			}
		}

		/// <summary>
		/// Hold the link until peer closes, read error, or Stop/Disconnect.
		/// Does not interpret payloads (no heartbeat / tick / DOM / orders).
		/// </summary>
		private void MonitorConnection()
		{
			TcpClient tcp;
			NetworkStream stream;
			lock (_gate)
			{
				tcp = _tcp;
				if (tcp == null || !_connected)
					return;
				try
				{
					stream = tcp.GetStream();
				}
				catch
				{
					return;
				}
			}

			while (_run && !_disposed)
			{
				lock (_gate)
				{
					if (_tcp != tcp || !_connected)
						return;
				}

				try
				{
					// Drain any inbound bytes; framing/validation stays on the Python side.
					// Read 0 => peer closed the session.
					int n = stream.Read(_recvBuffer, 0, _recvBuffer.Length);
					if (n <= 0)
					{
						Log("HOTIRJAM GatewayClient peer closed");
						return;
					}
				}
				catch (Exception ex)
				{
					if (!_run || _disposed)
						return;

					SocketException socketEx = ex as SocketException;
					if (socketEx != null && socketEx.SocketErrorCode == SocketError.TimedOut)
						continue;

					IOException ioEx = ex as IOException;
					if (ioEx != null)
					{
						SocketException inner = ioEx.InnerException as SocketException;
						if (inner != null && inner.SocketErrorCode == SocketError.TimedOut)
							continue;
					}

					Log("HOTIRJAM GatewayClient link lost: " + ex.Message);
					return;
				}
			}
		}

		private void SleepInterruptible(int totalMs)
		{
			int left = totalMs;
			while (left > 0 && _run && !_disposed)
			{
				int slice = left > 200 ? 200 : left;
				Thread.Sleep(slice);
				left -= slice;
			}
		}

		private void Log(string message)
		{
			Action<string> log = _log;
			if (log == null)
				return;
			try
			{
				log(message);
			}
			catch
			{
				// Never let logging break the link supervisor.
			}
		}

		private void ThrowIfDisposed()
		{
			if (_disposed)
				throw new ObjectDisposedException("GatewayClient");
		}
	}
}
