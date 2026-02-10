use std::env;
use std::fs;
use std::io::BufWriter;
use std::process;

use vibe_emu_core::cartridge::Cartridge;
use vibe_emu_core::gameboy::GameBoy;

const GB_FPS: f64 = 59.7275;
const SCREEN_WIDTH: u32 = 160;
const SCREEN_HEIGHT: u32 = 144;

// Maximum CPU steps per frame to prevent infinite loops.
// Normally a frame should complete in ~17556 steps (70224 cycles / 4 cycles per instruction average).
// We allow significantly more steps (100000) as a safety margin before giving up on a frame.
const MAX_STEPS_PER_FRAME: u64 = 100000;

fn usage() -> ! {
    eprintln!(
        "Usage: vibeemu-render <rom> <output.png> [options]\n\
         Options:\n\
         --model dmg|cgb    Hardware model (default: auto-detect from ROM)\n\
         --frames N         Number of frames to run (default: computed from --seconds)\n\
         --seconds N        Seconds of emulation (default: 30)\n\
         --bootrom PATH     Path to boot ROM"
    );
    process::exit(1);
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        usage();
    }

    let rom_path = &args[1];
    let output_path = &args[2];

    let mut model: Option<String> = None;
    let mut frames: Option<usize> = None;
    let mut seconds: Option<f64> = None;
    let mut bootrom_path: Option<String> = None;

    let mut i = 3;
    while i < args.len() {
        match args[i].as_str() {
            "--model" => {
                i += 1;
                model = Some(args.get(i).unwrap_or_else(|| usage()).clone());
            }
            "--frames" => {
                i += 1;
                frames = Some(
                    args.get(i)
                        .unwrap_or_else(|| usage())
                        .parse()
                        .unwrap_or_else(|_| usage()),
                );
            }
            "--seconds" => {
                i += 1;
                seconds = Some(
                    args.get(i)
                        .unwrap_or_else(|| usage())
                        .parse()
                        .unwrap_or_else(|_| usage()),
                );
            }
            "--bootrom" => {
                i += 1;
                bootrom_path = Some(args.get(i).unwrap_or_else(|| usage()).clone());
            }
            _ => {
                eprintln!("Unknown option: {}", args[i]);
                usage();
            }
        }
        i += 1;
    }

    // Load ROM
    let rom_data = fs::read(rom_path).unwrap_or_else(|e| {
        eprintln!("Failed to read ROM '{}': {}", rom_path, e);
        process::exit(1);
    });

    let cart = Cartridge::load(rom_data);

    // Determine CGB mode
    let cgb = match model.as_deref() {
        Some("dmg") | Some("DMG") => false,
        Some("cgb") | Some("CGB") => true,
        Some(other) => {
            eprintln!("Unknown model '{}', expected 'dmg' or 'cgb'", other);
            process::exit(1);
        }
        None => cart.cgb,
    };

    // Create GameBoy
    let mut gb = GameBoy::new_with_mode(cgb);

    // Load boot ROM if provided
    if let Some(ref path) = bootrom_path {
        let boot_data = fs::read(path).unwrap_or_else(|e| {
            eprintln!("Failed to read boot ROM '{}': {}", path, e);
            process::exit(1);
        });
        gb.mmu.load_boot_rom(boot_data);
        gb.reset_power_on();
    }

    // Use a neutral 4-shade grayscale DMG palette so the framebuffer output
    // matches the grayscale reference PNGs used by the test suite.
    // Set this after reset_power_on() since the reset recreates the MMU.
    if !cgb {
        gb.mmu.ppu.set_dmg_palette([0x00FFFFFF, 0x00AAAAAA, 0x00555555, 0x00000000]);
    }

    gb.mmu.load_cart(cart);

    // Determine how many frames to run
    let total_frames = if let Some(f) = frames {
        f
    } else {
        let secs = seconds.unwrap_or(30.0);
        (secs * GB_FPS).ceil() as usize
    };

    eprintln!(
        "Running {} for {} frames (model={})...",
        rom_path,
        total_frames,
        if cgb { "CGB" } else { "DMG" }
    );

    // Run emulation
    for frame_num in 0..total_frames {
        gb.mmu.ppu.clear_frame_flag();
        let mut steps_this_frame = 0u64;
        while !gb.mmu.ppu.frame_ready() {
            gb.cpu.step(&mut gb.mmu);
            steps_this_frame += 1;
            
            // Safety check: if we've exceeded the maximum steps per frame,
            // break out to prevent infinite loops (e.g., from STOP instruction).
            if steps_this_frame >= MAX_STEPS_PER_FRAME {
                eprintln!(
                    "Warning: Frame {} exceeded maximum step count ({} steps). Breaking out.",
                    frame_num, steps_this_frame
                );
                break;
            }
        }
    }

    // Extract framebuffer and save as PNG
    let framebuffer = gb.mmu.ppu.framebuffer();
    save_framebuffer_png(framebuffer, output_path);

    eprintln!("Saved framebuffer to {}", output_path);
}

const RGB_BUFFER_SIZE: usize = (SCREEN_WIDTH * SCREEN_HEIGHT * 3) as usize;

fn save_framebuffer_png(framebuffer: &[u32], path: &str) {
    let file = fs::File::create(path).unwrap_or_else(|e| {
        eprintln!("Failed to create output file '{}': {}", path, e);
        process::exit(1);
    });
    let writer = BufWriter::new(file);

    let mut encoder = png::Encoder::new(writer, SCREEN_WIDTH, SCREEN_HEIGHT);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);

    let mut png_writer = encoder.write_header().unwrap_or_else(|e| {
        eprintln!("Failed to write PNG header: {}", e);
        process::exit(1);
    });

    // Convert 0x00RRGGBB u32 framebuffer to RGB bytes
    let mut rgb_data = Vec::with_capacity(RGB_BUFFER_SIZE);
    for &pixel in framebuffer {
        let r = ((pixel >> 16) & 0xFF) as u8;
        let g = ((pixel >> 8) & 0xFF) as u8;
        let b = (pixel & 0xFF) as u8;
        rgb_data.push(r);
        rgb_data.push(g);
        rgb_data.push(b);
    }

    png_writer.write_image_data(&rgb_data).unwrap_or_else(|e| {
        eprintln!("Failed to write PNG data: {}", e);
        process::exit(1);
    });
}
