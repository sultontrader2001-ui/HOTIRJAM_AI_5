#region Using declarations
using System;
using System.Windows;
using HOTIRJAM.Gateway;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
#endregion

// HOTIRJAM Gateway — NinjaTrader 8 AddOn (TCP link to Python Gateway).
// Loads with NinjaTrader. Clean startup/shutdown.
// No Tick subscriptions. No DOM subscriptions. No Orders. No Broker API. No Trading Logic.

namespace NinjaTrader.NinjaScript.AddOns
{
	/// <summary>
	/// Standalone AddOn that hosts the HOTIRJAM <see cref="GatewayClient"/> TCP link.
	/// </summary>
	public class HotirjamGatewayAddOn : AddOnBase
	{
		// Must match the Python TransportServer listen address.
		private const string GatewayHost = "127.0.0.1";
		private const int GatewayPort = GatewayClient.DefaultPort;

		private GatewayClient _client;
		private bool _runtimeStarted;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description = "HOTIRJAM Gateway TCP client (no market data, no orders).";
				Name = "HOTIRJAM Gateway";
				WriteLog("HOTIRJAM AddOn Loaded");
			}
			else if (State == State.Terminated)
			{
				StopRuntime();
			}
		}

		protected override void OnWindowCreated(Window window)
		{
			if (!(window is ControlCenter))
				return;

			StartRuntime();
		}

		protected override void OnWindowDestroyed(Window window)
		{
			if (!(window is ControlCenter))
				return;

			StopRuntime();
		}

		private void StartRuntime()
		{
			if (_runtimeStarted)
				return;

			_client = new GatewayClient(GatewayHost, GatewayPort, WriteLog);
			_client.Start();
			_runtimeStarted = true;
			WriteLog("HOTIRJAM AddOn Started");
		}

		private void StopRuntime()
		{
			if (_client != null)
			{
				_client.Stop();
				_client.Dispose();
				_client = null;
			}

			if (!_runtimeStarted)
				return;

			_runtimeStarted = false;
			WriteLog("HOTIRJAM AddOn Stopped");
		}

		private void WriteLog(string message)
		{
			try
			{
				Print(message);
			}
			catch
			{
				try
				{
					NinjaTrader.Code.Output.Process(message, PrintTo.OutputTab1);
				}
				catch
				{
					// Keep NinjaTrader stable if logging is unavailable during early load.
				}
			}
		}
	}
}
