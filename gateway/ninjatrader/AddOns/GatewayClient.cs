#region Using declarations
using System;
#endregion

// HOTIRJAM Gateway — Windows-side client skeleton (Sprint NT-1).
// No sockets yet. No Tick/DOM. No orders. No broker API. No trading logic.

namespace HOTIRJAM.Gateway
{
	/// <summary>
	/// Hosts the future Gateway transport connection from NinjaTrader.
	/// Sprint NT-1: lifecycle skeleton only.
	/// </summary>
	public sealed class GatewayClient : IDisposable
	{
		private bool _started;
		private bool _disposed;

		/// <summary>True after <see cref="Start"/> and before <see cref="Stop"/>.</summary>
		public bool IsStarted
		{
			get { return _started; }
		}

		/// <summary>
		/// Begin client lifecycle. Future sprints open the Gateway transport here.
		/// </summary>
		public void Start()
		{
			ThrowIfDisposed();
			if (_started)
				return;

			_started = true;
		}

		/// <summary>
		/// End client lifecycle. Future sprints close the Gateway transport here.
		/// </summary>
		public void Stop()
		{
			if (_disposed || !_started)
				return;

			_started = false;
		}

		public void Dispose()
		{
			if (_disposed)
				return;

			Stop();
			_disposed = true;
		}

		private void ThrowIfDisposed()
		{
			if (_disposed)
				throw new ObjectDisposedException("GatewayClient");
		}
	}
}
